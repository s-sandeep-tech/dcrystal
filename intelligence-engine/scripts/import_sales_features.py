"""Import verified historical feature vintages from JSON; never infer issue times."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.dialects.postgresql import insert
from src.db.connection import get_db_session
from src.db.models import SalesExternalFeature
from src.external.sales_features import validate_feature


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='JSON array of verified feature vintages')
    args = parser.parse_args()
    with open(args.file) as source:
        rows = [validate_feature(row) for row in json.load(source)]
    with get_db_session() as session:
        for start in range(0, len(rows), 1000):
            session.execute(insert(SalesExternalFeature).values(rows[start:start + 1000])
                            .on_conflict_do_nothing(index_elements=['id']))
    print(f'Validated {len(rows)} feature vintages; duplicates left unchanged.')


if __name__ == '__main__':
    main()
