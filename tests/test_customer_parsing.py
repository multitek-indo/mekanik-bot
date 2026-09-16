from app.customer import parse_bulk_machine_list


def test_bulk_machine_parser():
    rows = parse_bulk_machine_list('JUKI DDL | benang putus; Obras Pegasus | suara kasar')
    assert rows == [
        {'machine': 'JUKI DDL', 'problem': 'benang putus'},
        {'machine': 'Obras Pegasus', 'problem': 'suara kasar'},
    ]
