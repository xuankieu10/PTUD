def update_table():
    with open('frontend/src/components/TranscriptTable.tsx', 'r', encoding='utf-8') as f:
        content = f.read()

    # Replacements
    replacements = {
        'SubjectGrade': 'SubjectRecord',
        'item.mon || item.name': 'item.course_name',
        'item.mon': 'item.course_name',
        'item.diem ?? item.grade': 'item.grade',
        'item.diem': 'item.grade',
        'item.ly_do || item.reason': 'item.filter_reason',
        'item.ly_do': 'item.filter_reason',
        'item.code': 'item.course_code',
        'item.reason': 'item.filter_reason',
        'item.priority_reason': 'item.priority_reason',
        'item.priority_score': 'item.priority_score'
    }

    for k, v in replacements.items():
        content = content.replace(k, v)

    with open('frontend/src/components/TranscriptTable.tsx', 'w', encoding='utf-8') as f:
        f.write(content)

update_table()
