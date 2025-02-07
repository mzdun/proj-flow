# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.msg** defines ChangelogMessage and implements
the message for release commit.
"""

import re
from typing import Dict, List

from proj_flow.log import commit


class ChangelogMessage:
    def intro_lines(self) -> List[str]:
        return []

    def section_header(self, lines: List[str], header):
        lines.extend([f"### {header}", ""])

    def issue_link(self, ref: str) -> str:
        return ref

    def scope_text(self, scope: str) -> str:
        if len(scope):
            scope = f"{scope}: "
        return scope

    def summary(self, text: str) -> str:
        return text

    def short_hash_link(self, link: commit.Link) -> str:
        return link.short_hash

    def list_item(self, line_markup: str) -> str:
        return f"- {line_markup}"

    def nothing_to_report(self, lines: List[str]):
        lines.extend(["*Nothing to report.*", ""])

    def outro_lines(self, _: List[str]) -> None:
        pass

    def post_process(self, lines: List[str]):
        return "\n".join(lines)

    def link_str(self, link: commit.Link, show_breaking: bool):
        scope = ""
        if len(link.scope):
            scope = link.scope

        if show_breaking:
            if link.is_breaking:
                if len(scope):
                    scope = f"breaking, {scope}"
                else:
                    scope = f"breaking"
        scope = self.scope_text(scope)

        refs = ""
        for refs_name in link.references:
            refs_links = [
                self.issue_link(issue)
                for issue in link.references[refs_name]
                if issue != ""
            ]
            if len(refs_links) > 0:
                refs += f", {refs_name} "
                if len(refs_links) == 1:
                    refs += refs_links[0]
                else:
                    last = refs_links[-1]
                    listed = ", ".join(refs_links[:-1])
                    refs += f"{listed} and {last}"

        summary = self.summary(link.summary)
        return self.list_item(f"{scope}{summary} ({self.short_hash_link(link)}){refs}")

    def show_links(self, links: List[commit.Link], show_breaking: bool) -> List[str]:
        issues: Dict[str, List[str]] = {}
        for link in links:
            scope = link.scope
            if scope not in issues:
                issues[scope] = []
            issues[scope].append(self.link_str(link, show_breaking))
        result = []
        for scope in sorted(issues.keys()):
            result.extend(issues[scope])
        if len(result):
            result.append("")
        return result

    def format_changelog(self, log: commit.ChangeLog) -> str:
        lines = self.intro_lines()
        lines_marker = len(lines)

        breaking: List[str] = []

        for section in commit.TYPES:
            try:
                type_section = log[section.key]
            except KeyError:
                continue

            show_breaking = section.key != commit.BREAKING_CHANGE

            self.section_header(lines, section.header)
            lines.extend(self.show_links(type_section, show_breaking))
            breaking.extend(_find_breaking_notes(type_section))

        for section in sorted(log.keys()):
            if section in commit.KNOWN_TYPES:
                continue
            type_section = log[section]
            try:
                section_header = commit.ALL_TYPES[section]
            except KeyError:
                section_header = section

            self.section_header(lines, section_header)
            lines.extend(self.show_links(type_section, True))
            breaking.extend(_find_breaking_notes(type_section))

        if len(breaking):
            self.section_header(lines, "BREAKING CHANGES")
            lines.extend(breaking)

        if lines_marker == len(lines):
            self.nothing_to_report(lines)

        self.outro_lines(lines)

        return self.post_process(lines)


class CommitMessage(ChangelogMessage):
    def section_header(self, lines: List[str], header):
        lines.extend([f"{header}:", ""])

    def list_item(self, line_markup: str):
        return f" - {line_markup}"

    def post_process(self, lines: List[str]):
        paras = "\n".join(lines).strip().split("\n\n")

        text = "\n\n".join(CommitMessage.wrap_at_78(para) for para in paras)
        if len(text):
            text = f"\n\n{text}"
        return text

    @staticmethod
    def wrap_at_78(para: str):
        if para[:3] == " - ":
            lines = para.split("\n")
            lines = [
                CommitMessage._wrap_at(75, line[3:], " - ", "   ") for line in lines
            ]
            return "\n".join(lines)
        return CommitMessage._wrap_at(78, para, "", "")

    @staticmethod
    def _wrap_at(length: int, para: str, firstLine: str, nextLines: str):
        result = ""
        line = firstLine
        lineIsDirty = False
        words = para.strip().split(" ")
        for word in words:
            wordLen = len(word)
            if wordLen == 0:
                continue

            lineIsDirty = True
            lineLen = len(line)
            space = " " if lineLen > 0 and line[-1] != " " else ""
            resultingLen = lineLen + len(space) + wordLen
            if resultingLen <= length:
                line = f"{line}{space}{word}"
                continue
            result = f"{result}{line}\n"
            line = f"{nextLines}{word}"

        if lineIsDirty:
            result = f"{result}{line}"
        return result


class ReleaseMessage(ChangelogMessage):
    setup: commit.LogSetup

    def __init__(self, setup: commit.LogSetup):
        self.setup = setup

    def scope_text(self, scope: str):
        if len(scope):
            scope = f"**{scope}**: "
        return scope

    def short_hash_link(self, link: commit.Link):
        url = self.setup.single_commit_link(link)
        if not url:
            return link.short_hash
        return f"[{link.short_hash}]({url})"

    def outro_lines(self, lines: List[str]) -> None:
        url = self.setup.commit_listing_link()
        if url:
            lines.append(f"**Full Changelog**: {url}")


def _find_breaking_notes(links: List[commit.Link]) -> List[str]:
    breaking: List[str] = []
    for link in links:
        if link.breaking_message is None:
            continue
        for para in link.breaking_message:
            text = re.sub(r"\s+", " ", para.strip())
            if text != "":
                breaking.append(text + "\n")
    return breaking


def format_commit_message(log: commit.ChangeLog):
    return CommitMessage().format_changelog(log)
