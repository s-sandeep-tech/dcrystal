from sqlalchemy import text
from app.extensions import db
from app.queries.section_wise_provision_stock_summary_queries import (
    SectionWiseProvisionStockSummaryQuery,
)


class SectionWiseProvisionStockSummaryData:
    """Database access owned by the Section-wise Provision and Stock Summary report."""

    @staticmethod
    def _fetch_rows(statement, params=None):
        query = text(statement) if isinstance(statement, str) else statement
        result = db.session.execute(query, params or {})
        return [dict(row._mapping) for row in result]

    @classmethod
    def latest_snapshot_date(cls):
        rows = cls._fetch_rows(
            SectionWiseProvisionStockSummaryQuery.LATEST_SNAPSHOT_DATE
        )
        return rows[0]['snapshot_date'] if rows else None

    @classmethod
    def authorized_branch_ids(cls, user_id):
        try:
            emp_code = int(user_id)
        except (TypeError, ValueError):
            return []
        rows = cls._fetch_rows(
            SectionWiseProvisionStockSummaryQuery.AUTHORIZED_BRANCH_IDS,
            {'emp_code': emp_code},
        )
        return [row['branch_id'] for row in rows]

    @staticmethod
    def _scope_params(scope):
        branch_ids = scope.get('authorized_branch_ids')
        return {
            'branch_type': scope.get('branch_type'),
            'business_head_emp_code': scope.get('business_head_emp_code'),
            'authorized_branch_ids': (
                ','.join(map(str, branch_ids)) if branch_ids else None
            ),
            'deny_all': bool(scope.get('deny_all')),
        }

    @classmethod
    def fetch_filter_options(cls, **scope):
        rows = cls._fetch_rows(
            SectionWiseProvisionStockSummaryQuery.FILTER_OPTIONS,
            cls._scope_params(scope),
        )
        row = rows[0] if rows else {}
        return {
            'divisions': row.get('divisions') or [],
            'locations': row.get('locations') or [],
            'purities': [float(value) for value in row.get('purities') or []],
            'classifications': row.get('classifications') or [],
            'sections': row.get('sections') or [],
            'prov_types': row.get('prov_types') or [],
            'provision_modes': row.get('provision_modes') or [],
            'branch_types': row.get('branch_types') or [],
            'branch_statuses': row.get('branch_statuses') or [],
            'business_heads': row.get('business_heads') or [],
            'states': row.get('states') or [],
        }

    @classmethod
    def search_collections(cls, search='', division=None, **scope):
        params = cls._scope_params(scope)
        params['search'] = f'%{search}%' if search else None
        params['division'] = division if division else None
        rows = cls._fetch_rows(
            SectionWiseProvisionStockSummaryQuery.SEARCH_COLLECTIONS,
            params,
        )
        return [row['value'] for row in rows]

    @classmethod
    def search_makes(cls, search='', division=None, **scope):
        params = cls._scope_params(scope)
        params['search'] = f'%{search}%' if search else None
        params['division'] = division if division else None
        rows = cls._fetch_rows(
            SectionWiseProvisionStockSummaryQuery.SEARCH_MAKES,
            params,
        )
        return [row['value'] for row in rows]

    @classmethod
    def fetch_summary_rows(cls, params):
        return cls._fetch_rows(
            SectionWiseProvisionStockSummaryQuery.SUMMARY,
            params,
        )

