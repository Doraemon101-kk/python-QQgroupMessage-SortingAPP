"""Literal, case-sensitive word counts over selected upstream records."""
from .models import Corpus, Occurrence, StudyConfig, StudyResult, validate_groups


def analyze(corpus: Corpus, config: StudyConfig) -> StudyResult:
    if config.case_sensitive is not True:
        raise ValueError('首版只支持区分大小写的字面匹配')
    if not config.terms or any(not isinstance(term, str) or not term.strip()
                               for term in config.terms):
        raise ValueError('至少提供一个非空研究词')
    terms = tuple(dict.fromkeys(config.terms))
    groups = validate_groups(config.term_groups, terms)

    def empty_counts():
        return {term: {'occurrences': 0, 'hit_messages': 0} for term in (*terms, *groups)}

    totals = empty_counts()
    monthly = {}
    occurrences = []
    any_hit_messages = 0
    for index in corpus.eligible_indices:
        message = corpus.messages[index]
        day = message.time[:10]
        month = day[:7]
        if month not in monthly:
            monthly[month] = {
                'record_count': 0,
                'first_record_date': day,
                'last_record_date': day,
                'per_term': empty_counts(),
            }
        bucket = monthly[month]
        bucket['record_count'] += 1
        bucket['first_record_date'] = min(bucket['first_record_date'], day)
        bucket['last_record_date'] = max(bucket['last_record_date'], day)
        message_hit = False
        positions = {term: [] for term in terms}
        for term in terms:
            count = 0
            cursor = 0
            while True:
                start = message.text.find(term, cursor)
                if start == -1:
                    break
                end = start + len(term)
                positions[term].append((start, end))
                occurrences.append(Occurrence(
                    term=term, message_index=index,
                    start_offset=start, end_offset=end,
                    occurrence_id=f'occ-{len(occurrences) + 1:06d}',
                ))
                count += 1
                cursor = end
            if count:
                for counts in (totals[term], bucket['per_term'][term]):
                    counts['occurrences'] += count
                    counts['hit_messages'] += 1
                message_hit = True
        for label, members in groups.items():
            spans = sorted({span for term in members for span in positions[term]})
            # Overlapping aliases describe one mention; touching spans remain separate.
            merged = []
            for start, end in spans:
                if merged and start < merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
                else:
                    merged.append((start, end))
            if merged:
                for counts in (totals[label], bucket['per_term'][label]):
                    counts['occurrences'] += len(merged)
                    counts['hit_messages'] += 1
        any_hit_messages += int(message_hit)

    return StudyResult(
        record_count=len(corpus.eligible_indices),
        any_hit_messages=any_hit_messages,
        per_term=totals,
        monthly=dict(sorted(monthly.items())),
        occurrences=occurrences,
        term_groups=groups,
    )
