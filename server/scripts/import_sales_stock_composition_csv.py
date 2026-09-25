import sys
import os
import csv
import time
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.sales_stock_composition_analysis import SalesStockCompositionAnalysisSnapshot


def to_decimal(val):
    if val is None or val == '' or str(val).upper() == 'NULL':
        return Decimal('0')
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def to_int(val):
    if val is None or val == '' or str(val).upper() == 'NULL':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def to_str(val):
    if val is None or str(val).upper() == 'NULL':
        return None
    s = str(val).strip()
    return s if s else None


def to_date(val):
    if not val or str(val).upper() == 'NULL':
        return None
    try:
        return date.fromisoformat(val[:10])
    except Exception:
        return None


def to_datetime(val):
    if not val or str(val).upper() == 'NULL' or str(val).startswith('0001-01-01'):
        return None
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return None


def run_import(filepath=None, truncate=True):
    app = create_app()
    with app.app_context():
        start_time = time.time()
        SalesStockCompositionAnalysisSnapshot.__table__.create(db.engine, checkfirst=True)

        if truncate:
            deleted = db.session.query(SalesStockCompositionAnalysisSnapshot).delete()
            db.session.commit()
            print(f"Cleared existing {deleted} rows from sales_stock_composition_analysis_snapshots.")

        if filepath and filepath != '-':
            print(f"Opening CSV file: {filepath}")
            f = open(filepath, mode='r', encoding='utf-8', errors='replace')
        else:
            print("Reading CSV from standard input...")
            f = sys.stdin

        try:
            reader = csv.DictReader(f)
            records = []
            now = datetime.utcnow()
            total_read = 0

            for row in reader:
                records.append({
                    'source_id': to_int(row.get('id')),
                    'date': to_date(row.get('date')),
                    'branch_id': to_int(row.get('branch_id')),
                    'location_name': to_str(row.get('location_name')),
                    'state_name': to_str(row.get('state_name')),
                    'item_definition_id': to_int(row.get('item_definition_id')),
                    'make': to_str(row.get('make')),
                    'make_id': to_int(row.get('make_id')),
                    'master_collection': to_str(row.get('master_collection')),
                    'master_collection_id': to_int(row.get('master_collection_id')),
                    'collection': to_str(row.get('collection')),
                    'collection_id': to_int(row.get('collection_id')),
                    'sub_section': to_str(row.get('sub_section')),
                    'sub_section_id': to_int(row.get('sub_section_id')),
                    'classification': to_str(row.get('classification')),
                    'classification_id': to_int(row.get('classification_id')),
                    'section': to_str(row.get('section')),
                    'section_id': to_int(row.get('section_id')),
                    'type': to_str(row.get('type')),
                    'type_id': to_int(row.get('type_id')),
                    'group': to_str(row.get('group')),
                    'group_id': to_int(row.get('group_id')),
                    'group_category': to_str(row.get('group_category')),
                    'group_category_id': to_int(row.get('group_category_id')),
                    'sub_classification': to_str(row.get('sub_classification')),
                    'sub_classification_id': to_int(row.get('sub_classification_id')),
                    'division': to_str(row.get('division')),
                    'division_id': to_int(row.get('division_id')),
                    'purity': to_decimal(row.get('purity')),
                    'purity_id': to_int(row.get('purity_id')),
                    'gender': to_str(row.get('gender')),
                    'gender_id': to_int(row.get('gender_id')),
                    'screw_type': to_str(row.get('screw_type')),
                    'screw_type_id': to_int(row.get('screw_type_id')),
                    'wide_range': to_str(row.get('wide_range')),
                    'wide_range_id': to_int(row.get('wide_range_id')),
                    'size_label': to_str(row.get('size_label')),
                    'size_unit': to_str(row.get('size_unit')),
                    'size_id': to_int(row.get('size_id')),
                    'barcode': to_str(row.get('barcode')),
                    'gross_weight': to_decimal(row.get('gross_weight')),
                    'net_weight': to_decimal(row.get('net_weight')),
                    'barcode_total_cost': to_decimal(row.get('barcode_total_cost')),
                    'purchase_cost': to_decimal(row.get('purchase_cost')),
                    'purchase_board_rate': to_decimal(row.get('purchase_board_rate')),
                    'provision_qty': to_int(row.get('provision_qty')) or 0,
                    'weight': to_decimal(row.get('weight')),
                    'provision_weight': to_decimal(row.get('provision_weight')),
                    'report_group': to_str(row.get('report_group')),
                    'invoice_type': to_str(row.get('invoice_type')),
                    'trans_type': to_str(row.get('trans_type')),
                    'l1_category': to_str(row.get('l1_category')),
                    'l2_category_type': to_str(row.get('l2_category_type')),
                    'l3_category_code': to_str(row.get('l3_category_code')),
                    'purchase_metal_value': to_decimal(row.get('purchase_metal_value')),
                    'purchase_mc_value': to_decimal(row.get('purchase_mc_value')),
                    'sale_mc_value': to_decimal(row.get('sale_mc_value')),
                    'gross_mc_value': to_decimal(row.get('gross_mc_value')),
                    'rate_tsk': to_decimal(row.get('rate_tsk')),
                    'turn_over': to_decimal(row.get('turn_over')),
                    'tsk': to_decimal(row.get('tsk')),
                    'total_tsk': to_decimal(row.get('total_tsk')),
                    'tax_app_trans_amount': to_decimal(row.get('tax_app_trans_amount')),
                    'total_tsk_plusit_charge': to_decimal(row.get('total_tsk_plusit_charge')),
                    'dhanteras_advance_yn': to_str(row.get('dhanteras_advance_yn')),
                    'dhanteras_red_benefit_yn': to_str(row.get('dhanteras_red_benefit_yn')),
                    'anbaana_advance_yn': to_str(row.get('anbaana_advance_yn')),
                    'anbaana_red_benefit_yn': to_str(row.get('anbaana_red_benefit_yn')),
                    'myk_sourced_yn': to_str(row.get('myk_sourced_yn')),
                    'ornament_category': to_str(row.get('ornament_category')),
                    'last_updated_at': to_datetime(row.get('last_updated_at')),
                    'uid': to_str(row.get('uid')),
                    'synced_at': now
                })
                total_read += 1

                if len(records) >= 2000:
                    db.session.bulk_insert_mappings(SalesStockCompositionAnalysisSnapshot, records)
                    db.session.commit()
                    print(f"Inserted {total_read:,} records...")
                    records = []

            if records:
                db.session.bulk_insert_mappings(SalesStockCompositionAnalysisSnapshot, records)
                db.session.commit()
                print(f"Inserted final batch. Total: {total_read:,} records.")

            duration = time.time() - start_time
            print(f"Import completed successfully in {duration:.2f} seconds! Total records: {total_read:,}")
        finally:
            if filepath and filepath != '-':
                f.close()


if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv) > 1 else '-'
    run_import(csv_path)
