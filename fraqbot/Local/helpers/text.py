import re

from tabulate import tabulate


def format_table(data, fields=None, margin=None, sep=None, border=None):
    if not fields or not isinstance(fields, list):
        field_order = sorted(data[0].keys())
        fields = {f: {} for f in field_order}
    else:
        field_order = [f['field'] for f in fields]
        fields = {f['field']: f for f in fields}

    data.insert(0, {
        f: fields.get(f, {}).get('display', f)
        for f in field_order
    })

    for f, info in fields.items():
        info['max'] = max(len(str(d.get(f, ''))) for d in data)

    margin = margin if margin and isinstance(margin, int) else 0
    sep = sep if sep and isinstance(sep, str) else ''
    border = border if border and isinstance(border, str) else ''

    lines = []
    for d in data:
        line = []
        for f in field_order:
            item = str(d.get(f, ''))
            while len(item) < fields[f]['max']:
                item = f'{item} '

            for _ in range(margin):
                item = f' {item} '

            line.append(item)

        line = f'{border}{sep.join(line)}{border}'

        lines.append(line)

    if border:
        border_line = ''
        for _ in range(len(lines[0])):
            border_line = f'{border_line}{border}'

        lines.insert(0, border_line)
        lines.insert(2, border_line)
        lines.append(border_line)

    return '\n'.join(lines)


def snake_to_pascal(item):
    if not isinstance(item, str):
        return item

    out = []
    for word in re.split(r'[A-Z_]', item):
        if len(word) == 1:
            out.append(word.upper())
        else:
            out.append('{}{}'.format(word[0].upper(), word[1:].lower()))

    return ''.join(out)


def tabulate_data(data, _map, fields=None, user_id_field=None, thread=None):
    if not fields or not isinstance(fields, (list, str)):
        fields = sorted(list(set([
            k for d in data
            for k in d.keys()
        ])))

    if isinstance(fields, str):
        fields = sorted([f.strip() for f in fields.split(',')])

    user_replace = user_id_field and thread and user_id_field in fields
    idx = fields.index(user_id_field) if user_replace else 0
    new_data = []

    for d in data:
        record = []
        for field in fields:
            record.append(d.get(field, ''))
            if user_replace and field == user_id_field:
                name = thread.get_user_name_by_id(record[-1], True)
                record.append(name if name else None)

        if user_replace:
            if record[idx + 1]:
                new_data.append(record)

        else:
            new_data.append(record)

    if user_replace:
        table_data = [
            [
                '@{}'.format(d[idx + 1]) if i == idx else item
                for i, item in enumerate(d)
                if i != idx + 1
            ]
            for d in new_data
        ]

    mapped_fields = [_map.get(f, f) for f in fields]

    out = tabulate(
        [mapped_fields] + table_data, headers='firstrow', tablefmt='github')

    if user_replace:
        for d in new_data:
            out = out.replace(
                '@{}'.format(d[idx + 1]),
                '<@{}>'.format(d[idx])
            )

    return f'```{out}```'


def parse_message_params(text, delimiter=None, fields=None):
    delimiter = delimiter if delimiter else r'\s+'

    params = re.split(delimiter, text)

    if fields:
        out = {}
        for f in fields:
            out[f] = params.pop(0) if params else None
    else:
        out = params

    return out
