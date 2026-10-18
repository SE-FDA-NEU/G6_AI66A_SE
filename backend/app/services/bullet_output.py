"""Finalize recommendations after shared evidence verification."""

INSUFFICIENT_ACTIONS = 'Tài liệu không đủ căn cứ nguồn để hỗ trợ hai hành động đề xuất.'


def finalize_bullet_actions(output, warnings, language="vi"):
    supported, seen = [], set()
    for action in output.actions:
        identity = ' '.join((action.text or '').casefold().split())
        if not identity or action.unverified or not action.evidence or action.verification_issues or identity in seen:
            continue
        supported.append(action)
        seen.add(identity)
    output.actions = supported
    if len(supported) < 2:
        # Server-owned wording remains explicit even if a model omits a limitation.
        output.limitation = ("The document does not provide enough source evidence to support two recommended actions."
                             if language == "en" else INSUFFICIENT_ACTIONS)
        if 'insufficient_actions' not in warnings:
            warnings.append('insufficient_actions')
    else:
        output.limitation = None
        warnings[:] = [warning for warning in warnings if warning != 'insufficient_actions']
    # A fallback limitation counts towards the same public word budget.
    return type(output).model_validate(output.model_dump())
