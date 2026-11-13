"""Purpose-built V2 wire reproduction, not the owner's private Sol/Astra history."""
from contextlib import contextmanager
from copy import deepcopy

from .subagent_sessions import assistant, incident_source, link, user


@contextmanager
def recursive_source():
    with incident_source() as (source, server):
        template = server.sessions[1]
        for identity, parent in (("ses_sibling", "ses_current"), ("ses_other", "ses_current"),
                                 ("ses_nested", "ses_current_child"), ("ses_great", "ses_nested")):
            server.sessions.append({**template, "id": identity, "parentID": parent})
        links = [dict(link(child=identity, start=3250), id=identity, callID=identity)
                 for identity in ("ses_sibling", "ses_other")]
        server.messages["ses_current"][1]["content"].extend((*links, deepcopy(links[0])))
        server.messages["ses_current_child"][1]["content"] = [
            dict(link(child="ses_nested", start=3450, end=3700), id="nested", callID="nested")]
        server.messages["ses_nested"] = [user("nu", 3460), assistant("na", 3500, 3650, content=[
            dict(link(child="ses_great", start=3550, end=3560, background=True), id="great", callID="great")])]
        server.messages["ses_great"] = [user("gu", 4800), assistant("ga", 4850, 5000)]
        # Independent siblings deliberately share time/model/tokens, not identity.
        server.messages["ses_sibling"] = [user("su", 3300), assistant("sa", 3400, 3800, model="claude-test")]
        other = assistant("oa", 3400, 3800)
        other["model"].update(providerID="openai", variant="medium")
        server.messages["ses_other"] = [user("ou", 3300), other]
        server.messages["ses_current"].extend((user("u2", 4600), assistant("a3", 4700, 4900)))
        server.messages["ses_current_child"].append(assistant("outside", 6000, 6200, model="claude-test"))
        yield source, server
