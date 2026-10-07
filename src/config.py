"""Configuration loading, compatibility normalization and startup validation.

The v78 configuration contract intentionally preserves the useful v77 semantics:
omitted properties inherit defaults, explicit JSON null remains an override, user
objects merge recursively, color schemes resolve after validation, and malformed
configuration fails before runtime integrations start.
"""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

CONSOLE_COLORS = {
    "black", "darkblue", "darkgreen", "darkcyan", "darkred", "darkmagenta",
    "darkyellow", "gray", "darkgray", "blue", "green", "cyan", "red",
    "magenta", "yellow", "white",
}
OPEN_CODE_SOURCES = {"auto", "v1", "v2"}
BUILTIN_COLOR_SCHEMES = ("classic", "modus-operandi-tinted")


class ConfigError(ValueError):
    """Actionable, secret-safe configuration failure."""


@dataclass(frozen=True)
class LoadedConfig:
    """Validated effective configuration plus its source paths."""

    values: Mapping[str, Any]
    default_path: Path
    user_path: Path
    user_config_present: bool

    @property
    def open_code_source(self) -> str:
        return str(self.values["openCode"]["source"])


def remove_json_comments(text: str) -> str:
    """Remove // and /* */ comments without touching comment markers in strings."""
    out: list[str] = []
    in_string = False
    escaped = False
    line_comment = False
    block_comment = False
    i = 0
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
                out.append(char)
            i += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            i += 1
            continue
        if char == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if char == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


def read_jsonc(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(remove_json_comments(raw))
    except (OSError, UnicodeError, ValueError) as exc:
        # Never echo parser excerpts: user config may contain credential paths/secrets.
        raise ConfigError(
            f"File: {path.name}\nSetting: JSONC\n"
            "Invalid JSONC or unreadable file. Check JSON syntax, comments and file permissions."
        ) from exc
    if not isinstance(value, dict):
        raise ConfigError(f"File: {path.name}\nSetting: JSONC\nExpected: a JSON object")
    return value


def merge_config(defaults: Any, overrides: Any) -> Any:
    """Recursive v77-compatible merge: omitted inherits; explicit null overrides."""
    if overrides is None:
        return None
    if defaults is None:
        return copy.deepcopy(overrides)
    if not isinstance(defaults, dict) or not isinstance(overrides, dict):
        return copy.deepcopy(overrides)
    result: dict[str, Any] = {}
    for name, default_value in defaults.items():
        if name in overrides:
            result[name] = merge_config(default_value, overrides[name])
        else:
            result[name] = copy.deepcopy(default_value)
    for name, override_value in overrides.items():
        if name not in result:
            result[name] = copy.deepcopy(override_value)
    return result


def _setting_source(path: str, overrides: Mapping[str, Any]) -> str:
    node: Any = overrides
    for part in path.split(".") if path else ():
        if not isinstance(node, dict):
            return "config/user-config.jsonc"
        if part not in node:
            return "config/default-config.jsonc"
        node = node[part]
    return "config/user-config.jsonc" if path else "config/default-config.jsonc"


def _safe_value(path: str, value: Any) -> str:
    if path == "colorScheme" or path.startswith("colors.") or path.startswith("colorSchemes."):
        if isinstance(value, str) and 1 <= len(value) <= 30 and all(c.isalnum() or c in "_-" for c in value):
            return json.dumps(value)
        if value is None:
            return "null"
        if isinstance(value, bool) or (isinstance(value, int) and not isinstance(value, bool)):
            return str(value)
    return "(omitted for security)"


def _invalid(source: str, path: str, value: Any, expected: str) -> ConfigError:
    return ConfigError(
        f"File: {source}\nSetting: {path or 'root'}\nInvalid value: {_safe_value(path, value)}\nExpected: {expected}"
    )


def _assert_object(value: Any, path: str, allowed: set[str], source: str) -> None:
    if not isinstance(value, dict):
        raise _invalid(source, path, value, "a JSON object")
    unknown = [name for name in value if name not in allowed]
    if unknown:
        key = f"{path}.{unknown[0]}" if path else unknown[0]
        raise _invalid(source, key, value[unknown[0]],
                       "a recognized property (this setting is not recognized): " + ", ".join(sorted(allowed)))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _assert_number(value: Any, path: str, source: str, minimum: float, maximum: float, whole: bool = False) -> None:
    valid = _is_number(value) and minimum <= float(value) <= maximum
    if whole and valid:
        valid = float(value).is_integer()
    if not valid:
        kind = "an integer" if whole else "a number"
        raise _invalid(source, path, value, f"{kind} between {minimum} and {maximum}")


def _assert_color_style(value: Any, path: str, source: str, allow_null: bool = True) -> None:
    if value is None and allow_null:
        return
    _assert_object(value, path, {"foreground", "background", "ansi256"}, source)
    assert isinstance(value, dict)
    for channel in ("foreground", "background"):
        if channel not in value or value[channel] is None:
            continue
        color = value[channel]
        valid = isinstance(color, str) and color.strip() and color.lower() in CONSOLE_COLORS
        if not valid:
            raise _invalid(source, f"{path}.{channel}", color, "a ConsoleColor name or null")
    if "ansi256" in value and value["ansi256"] is not None:
        ansi = value["ansi256"]
        if not (isinstance(ansi, int) and not isinstance(ansi, bool) and 0 <= ansi <= 255):
            raise _invalid(source, f"{path}.ansi256", ansi, "an integer from 0 to 255, or null")


def normalize_legacy_settings(overrides: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(overrides)
    # Removed local budget: accept old configs without retaining active semantics.
    result.pop("monthlyAiCredits", None)
    if "pricingMaxAgeDays" in result:
        if "pricingMaxAgeHours" not in result:
            value = result["pricingMaxAgeDays"]
            if not _is_number(value) or float(value) < 0:
                raise ConfigError(
                    "File: config/user-config.jsonc\nSetting: pricingMaxAgeDays\n"
                    "Invalid legacy cache-age value. Replace it with a non-negative pricingMaxAgeHours number."
                )
            result["pricingMaxAgeHours"] = float(value) * 24.0
        del result["pricingMaxAgeDays"]
    return result


def validate_configuration(config: dict[str, Any], defaults: dict[str, Any], overrides: dict[str, Any]) -> None:
    root_keys = set(defaults)
    _assert_object(overrides, "", root_keys, "config/user-config.jsonc")
    _assert_object(config, "", root_keys, "config/default-config.jsonc")

    numeric = {
        "pricingMaxAgeHours": (0.0, float("inf"), False),
        "runningPromptWarningCCost": (0.0, float("inf"), False),
        "watchDashboardMaxRows": (-2147483648.0, 2147483647.0, True),
        "watchRecentEventSeconds": (-float("inf"), float("inf"), False),
    }
    for name, (minimum, maximum, whole) in numeric.items():
        _assert_number(config.get(name), name, _setting_source(name, overrides), minimum, maximum, whole)

    watch_interval = config.get("sessionWatchIntervalSeconds")
    if isinstance(watch_interval, str):
        if watch_interval.strip().lower() != "auto":
            raise _invalid(
                _setting_source("sessionWatchIntervalSeconds", overrides),
                "sessionWatchIntervalSeconds", watch_interval, '"auto" or an integer',
            )
        config["sessionWatchIntervalSeconds"] = "auto"
    else:
        _assert_number(
            watch_interval, "sessionWatchIntervalSeconds",
            _setting_source("sessionWatchIntervalSeconds", overrides),
            -2147483648.0, 2147483647.0, True,
        )

    timezone = config.get("timezone")
    if not isinstance(timezone, str) or not timezone.strip():
        raise _invalid(_setting_source("timezone", overrides), "timezone", timezone, "a non-empty time-zone ID")
    # Python's stdlib zoneinfo has no guaranteed IANA database on clean Windows.
    # Resolution is deliberately deferred to the later timezone/runtime utility;
    # Step 2 validates the safe, non-empty configuration contract without adding tzdata.
    if any(ord(c) < 32 for c in timezone):
        raise _invalid(_setting_source("timezone", overrides), "timezone", timezone, "a non-empty time-zone ID")

    workday = config.get("workdayCalendar")
    if not isinstance(workday, str):
        raise _invalid(_setting_source("workdayCalendar", overrides), "workdayCalendar", workday, "a string")

    for group, allowed in {
        "copilotQuota": {"enabled", "authJsonPath"},
        "openAiQuota": {"enabled", "authJsonPath"},
        "anthropicQuota": {"enabled", "authJsonPath"},
        "openrouterQuota": {"enabled", "authJsonPath"},
        "deepseekQuota": {"enabled", "authJsonPath"},
        "minimaxQuota": {"enabled", "authJsonPath"},
        # Legacy no-op accepted so v77/early-v78 user configs keep loading after
        # same-prompt comparison tables were removed from the terminal product.
        "matchedModelComparisons": {"enabled"},
        "openCode": {"source"},
    }.items():
        value = config.get(group)
        _assert_object(value, group, allowed, _setting_source(group, overrides))
        assert isinstance(value, dict)
        if group.endswith("Quota") or group == "matchedModelComparisons":
            if not isinstance(value.get("enabled"), bool):
                raise _invalid(_setting_source(f"{group}.enabled", overrides), f"{group}.enabled", value.get("enabled"), "true or false")

    for group in ("copilotQuota", "openAiQuota", "anthropicQuota", "openrouterQuota", "deepseekQuota", "minimaxQuota"):
        auth = config[group].get("authJsonPath")
        if auth is not None and not isinstance(auth, str):
            path = f"{group}.authJsonPath"
            raise _invalid(_setting_source(path, overrides), path, auth, "a string path or null")

    source = config["openCode"].get("source")
    if not isinstance(source, str) or source.strip().lower() not in OPEN_CODE_SOURCES:
        raise _invalid(_setting_source("openCode.source", overrides), "openCode.source", source, "auto, v1, or v2")
    config["openCode"]["source"] = source.strip().lower()

    default_thresholds = defaults.get("thresholds")
    thresholds = config.get("thresholds")
    if not isinstance(default_thresholds, dict):
        raise ConfigError("File: config/default-config.jsonc\nSetting: thresholds\nExpected: a JSON object")
    threshold_names = set(default_thresholds)
    _assert_object(thresholds, "thresholds", threshold_names, _setting_source("thresholds", overrides))
    assert isinstance(thresholds, dict)
    for name in threshold_names:
        path = f"thresholds.{name}"
        whole = name == "promptCostMinSamples"
        minimum = -2147483648.0 if whole else 0.0
        maximum = 2147483647.0 if whole else float("inf")
        if name.startswith("promptCostP") or name == "nextIctxPriceThresholdWarningPercent":
            minimum, maximum = 0.0, 100.0
        _assert_number(thresholds.get(name), path, _setting_source(path, overrides), minimum, maximum, whole)

    default_colors = defaults.get("colors")
    if not isinstance(default_colors, dict):
        raise ConfigError("File: config/default-config.jsonc\nSetting: colors\nExpected: a JSON object")
    color_keys = set(default_colors)

    default_schemes = defaults.get("colorSchemes")
    _assert_object(default_schemes, "colorSchemes", set(BUILTIN_COLOR_SCHEMES), "config/default-config.jsonc")
    assert isinstance(default_schemes, dict)
    for name in BUILTIN_COLOR_SCHEMES:
        palette = default_schemes.get(name)
        _assert_object(palette, f"colorSchemes.{name}", color_keys, "config/default-config.jsonc")
        assert isinstance(palette, dict)
        if set(palette) != color_keys:
            raise _invalid("config/default-config.jsonc", f"colorSchemes.{name}", palette, "a complete palette containing all registered color keys")
        for key in color_keys:
            _assert_color_style(palette[key], f"colorSchemes.{name}.{key}", "config/default-config.jsonc", allow_null=False)

    schemes = config.get("colorSchemes")
    if not isinstance(schemes, dict):
        raise _invalid(_setting_source("colorSchemes", overrides), "colorSchemes", schemes, "a JSON object")
    for required in BUILTIN_COLOR_SCHEMES:
        if required not in schemes:
            raise _invalid(_setting_source(f"colorSchemes.{required}", overrides), f"colorSchemes.{required}", None, "a complete built-in palette")
    for scheme_name, palette in schemes.items():
        path = f"colorSchemes.{scheme_name}"
        _assert_object(palette, path, color_keys, _setting_source(path, overrides))
        assert isinstance(palette, dict)
        if set(palette) != color_keys:
            raise _invalid(_setting_source(path, overrides), path, palette, "a complete palette containing all registered color keys")
        for key in color_keys:
            _assert_color_style(palette[key], f"{path}.{key}", _setting_source(f"{path}.{key}", overrides))

    colors = config.get("colors")
    if colors is not None:
        _assert_object(colors, "colors", color_keys, _setting_source("colors", overrides))
        assert isinstance(colors, dict)
        for key, value in colors.items():
            path = f"colors.{key}"
            if value is None:
                continue
            if isinstance(value, str):
                if value.strip().lower() != "default":
                    raise _invalid(_setting_source(path, overrides), path, value, '"default", null, or a color-style object')
            else:
                _assert_color_style(value, path, _setting_source(path, overrides), allow_null=False)

    scheme_name = config.get("colorScheme")
    matching = next((name for name in schemes if isinstance(scheme_name, str) and name.lower() == scheme_name.lower()), None)
    if matching is None:
        raise _invalid(_setting_source("colorScheme", overrides), "colorScheme", scheme_name, "a supported configured color scheme")
    config["colorScheme"] = matching


def resolve_colors(config: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(config)
    schemes = result["colorSchemes"]
    scheme_name = result["colorScheme"]
    palette = schemes[scheme_name]
    raw_colors = result.get("colors")
    if raw_colors is None:
        raw_colors = {}
    resolved: dict[str, Any] = {}
    for name, base_style in palette.items():
        if name not in raw_colors:
            resolved[name] = copy.deepcopy(base_style)
            continue
        override = raw_colors[name]
        if isinstance(override, str) and override.strip().lower() == "default":
            resolved[name] = copy.deepcopy(base_style)
        elif override is None:
            resolved[name] = None
        elif isinstance(override, dict):
            resolved[name] = merge_config(base_style, override)
        else:  # guarded by validation; kept fail-closed for direct callers
            raise ConfigError(f'colors.{name} must be "default", null, or a color-style object.')
    result["colors"] = resolved
    return result


def validate_resolved_colors(config: dict[str, Any], defaults: dict[str, Any], overrides: dict[str, Any]) -> None:
    keys = set(defaults["colors"])
    colors = config.get("colors")
    _assert_object(colors, "colors", keys, _setting_source("colors", overrides))
    assert isinstance(colors, dict)
    if set(colors) != keys:
        raise _invalid(_setting_source("colors", overrides), "colors", colors, "a complete resolved color map")
    for key in keys:
        _assert_color_style(colors[key], f"colors.{key}", _setting_source(f"colors.{key}", overrides))


def load_configuration(package_root: Path) -> LoadedConfig:
    default_path = package_root / "config" / "default-config.jsonc"
    user_path = package_root / "config" / "user-config.jsonc"
    if not default_path.is_file():
        raise ConfigError("File: config/default-config.jsonc\nSetting: file\nRequired configuration file is missing.")

    defaults = read_jsonc(default_path)
    # Shipped defaults must stand on their own; user overrides may never mask a bad package.
    validate_configuration(defaults, defaults, {})

    user_present = user_path.is_file()
    overrides = read_jsonc(user_path) if user_present else {}
    overrides = normalize_legacy_settings(overrides)
    effective = merge_config(defaults, overrides)
    if not isinstance(effective, dict):
        raise ConfigError("File: config/default-config.jsonc\nSetting: root\nExpected: a JSON object")
    validate_configuration(effective, defaults, overrides)
    resolved = resolve_colors(effective)
    validate_resolved_colors(resolved, defaults, overrides)
    return LoadedConfig(resolved, default_path, user_path, user_present)
