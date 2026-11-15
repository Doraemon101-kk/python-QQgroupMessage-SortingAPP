from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StudyConfig:
    terms: tuple[str, ...]
    start_date: str = ''
    end_date: str = ''
    context_radius: int = 3
    case_sensitive: bool = True
    term_groups: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Corpus:
    # Original objects and ordering from the live project; never serialize bodies by default.
    messages: tuple[Any, ...]
    eligible_indices: tuple[int, ...]
    skipped_records: int
    core_sha256: str
    input_sha256: str


@dataclass(frozen=True)
class Occurrence:
    term: str
    message_index: int
    start_offset: int
    end_offset: int
    occurrence_id: str


@dataclass
class StudyResult:
    record_count: int
    any_hit_messages: int
    # per_term: {term: {occurrences: int, hit_messages: int}}
    per_term: dict[str, dict[str, int]]
    # monthly: {YYYY-MM: {record_count: int, per_term: {...}}}
    monthly: dict[str, dict]
    occurrences: list[Occurrence] = field(default_factory=list)
    term_groups: dict[str, tuple[str, ...]] = field(default_factory=dict)


def validate_groups(groups, terms):
    if not isinstance(groups, dict):
        raise ValueError('term_groups 必须是分组名称到别名列表的对象')
    normalized = {}
    for label, members in groups.items():
        if not isinstance(label, str) or not label.strip() or label in terms:
            raise ValueError('分组名不能为空或与研究词重名')
        if not isinstance(members, (list, tuple)) or not members:
            raise ValueError('每个分组至少包含一个研究词')
        if any(not isinstance(t, str) or t not in terms for t in members):
            raise ValueError('分组成员必须来自 terms')
        normalized[label] = tuple(dict.fromkeys(members))
    return normalized
