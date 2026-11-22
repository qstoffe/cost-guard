"""Read short WAL snapshots of pinned Stats evidence on the background lane."""
from dataclasses import dataclass

from .display_stats_evidence import ResponseTiming, StatsMatch, response_timings
from .display_stats_revision import StatsVersion, retained_stats_version
from .display_usage_reader import USAGE_SLICE, UsageSlice, read_usage_slice


@dataclass(frozen=True, slots=True)
class StatsUsageSlice:
    version: StatsVersion
    population: UsageSlice
    responses: dict[bytes, ResponseTiming]


@dataclass(frozen=True, slots=True)
class StatsRootInput:
    root: str
    title: str
    revision: str
    usage_pending: bool
    first_input: StatsMatch | None


@dataclass(frozen=True, slots=True)
class StatsRootSlice:
    version: StatsVersion
    roots: tuple[StatsRootInput, ...]
    next_cursor: tuple[int, str] | None


def read_stats_usage(db, source, *, expected=None, after=None):
    version = retained_stats_version(db, source, expected)
    if version is None:
        return None
    population = read_usage_slice(db, source, expected=version.usage, after=after)
    responses = response_timings(db, source, tuple(entry.request_key for entry in population.entries),
                                through=version.evidence)
    return StatsUsageSlice(version, population, responses)


def read_stats_roots(db, source, *, expected=None, after=None):
    version = retained_stats_version(db, source, expected)
    if version is None:
        return None
    resume = "AND (stats.first_revision,stats.root_id)>(?,?)" if after is not None else ""
    rows = db.execute(f"""
        SELECT stats.first_revision,stats.root_id,sessions.title,stats.source_revision,stats.usage_pending,
               input.event_id,input.fingerprint,input.start_ms,input.duration_ms,input.status
        FROM archive_stats_roots AS stats INDEXED BY archive_stats_root_cohort
        CROSS JOIN sessions ON (sessions.source,sessions.session_id)=(stats.source,stats.root_id)
        LEFT JOIN archive_stats_first_inputs AS input ON (input.source,input.root_id)=(stats.source,stats.root_id)
                                                      AND input.first_revision<=?
        WHERE stats.source=? AND stats.first_revision<=? {resume}
        ORDER BY stats.first_revision,stats.root_id LIMIT ?
    """, (version.evidence, source, version.evidence, *(after or ()), USAGE_SLICE + 1)).fetchall()
    inputs = tuple(StatsRootInput(*row[1:4], bool(row[4]), StatsMatch(*row[5:]) if row[5] is not None else None)
                   for row in rows[:USAGE_SLICE])
    return StatsRootSlice(version, inputs, rows[USAGE_SLICE - 1][:2] if len(rows) > USAGE_SLICE else None)


def read_stats_parents(db, source, root, through, after=None):
    resume = "AND session_id>?" if after is not None else ""
    rows = db.execute(f"""
        SELECT session_id,parent_id FROM archive_stats_parents
        WHERE source=? AND root_id=? AND first_revision<=? {resume}
        ORDER BY session_id LIMIT ?
    """, (source, root, through, *((after,) if after is not None else ()), USAGE_SLICE + 1)).fetchall()
    return tuple(rows[:USAGE_SLICE]), rows[USAGE_SLICE - 1][0] if len(rows) > USAGE_SLICE else None
