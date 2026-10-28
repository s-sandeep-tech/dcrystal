import os
from datetime import datetime
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side

from app.services.section_wise_provision_stock_summary_data import (
    SectionWiseProvisionStockSummaryData,
)


class SectionWiseProvisionStockSummaryExport:
    """Excel export owned exclusively by Section-wise Provision and Stock Summary."""

    EXPORTS_DIR = '/app/uploads/exports'

    @classmethod
    def generate(cls, filters):
        os.makedirs(cls.EXPORTS_DIR, exist_ok=True)
        params = {
            key: filters.get(key) or None
            for key in (
                'division', 'location', 'state', 'purity', 'classification', 'make',
                'collection', 'section', 'prov_type', 'provision_mode',
                'branch_type', 'branch_status', 'business_head',
                'bh_emp_code', 'authorized_branch_ids',
            )
        }
        rows = SectionWiseProvisionStockSummaryData.fetch_summary_rows(params)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Section-wise Summary'

        headers = (
            'Level', 'Section', 'Make', 'Collection', 'Type', 'Wide Range',
            'Provision Pieces', 'Provision Gross Wt', 'In Shop Wt', 'Transit Wt',
            'Short Pieces', 'Excess Pieces', 'Short %', 'Short Wt', 'Excess Wt',
            'Net Short / Excess', 'Ordered Wt',
        )
        sheet.append(headers)

        header_fill = PatternFill('solid', fgColor='1E293B')
        header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1'),
        )

        for cell in sheet[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border = thin_border
        sheet.row_dimensions[1].height = 28

        level_labels = {
            0: 'Grand Total',
            1: 'Section',
            2: 'Make',
            3: 'Collection',
            4: 'Type',
            5: 'Wide Range',
        }

        level_fills = {
            0: PatternFill('solid', fgColor='E2E8F0'), # Grand Total
            1: PatternFill('solid', fgColor='F1F5F9'), # Section
            2: PatternFill('solid', fgColor='FFFFFF'),
            3: PatternFill('solid', fgColor='FFFFFF'),
            4: PatternFill('solid', fgColor='FFFFFF'),
            5: PatternFill('solid', fgColor='FFFFFF'),
        }

        for row in rows:
            level = row.get('level_id', 1)
            level_name = level_labels.get(level, f'Level {level}')

            # Indent section/name based on hierarchy level
            sec_val = row.get('section') if level >= 1 else 'Grand Total'
            make_val = row.get('make') if level >= 2 else ''
            coll_val = row.get('collection') if level >= 3 else ''
            typ_val = row.get('type') if level >= 4 else ''
            rng_val = row.get('wide_range') if level >= 5 else ''

            row_data = (
                level_name,
                sec_val,
                make_val,
                coll_val,
                typ_val,
                rng_val,
                float(row.get('prov_pcs') or 0),
                float(row.get('prov_gr_wt') or 0),
                float(row.get('in_shop_wt') or 0),
                float(row.get('in_transit_wt') or 0),
                float(row.get('short_pcs') or 0),
                float(row.get('excess_pcs') or 0),
                float(row.get('short_percent') or 0),
                float(row.get('short_wt') or 0),
                float(row.get('excess_wt') or 0),
                float(row.get('net_short_excess') or 0),
                float(row.get('ordered_wt') or 0),
            )
            sheet.append(row_data)

            current_row_idx = sheet.max_row
            row_fill = level_fills.get(level, PatternFill('solid', fgColor='FFFFFF'))
            is_bold = (level in [0, 1])

            for col_idx, cell in enumerate(sheet[current_row_idx], start=1):
                cell.border = thin_border
                cell.fill = row_fill
                cell.font = Font(name='Calibri', size=10, bold=is_bold)

                if col_idx <= 6:
                    cell.alignment = Alignment(horizontal='left', vertical='center')
                elif col_idx in [7, 11, 12]: # Pieces
                    cell.alignment = Alignment(horizontal='right', vertical='center')
                    cell.number_format = '#,##0'
                elif col_idx == 13: # Short %
                    cell.alignment = Alignment(horizontal='right', vertical='center')
                    cell.number_format = '0.0"%"'
                else: # Weights
                    cell.alignment = Alignment(horizontal='right', vertical='center')
                    cell.number_format = '#,##0.000'

        sheet.freeze_panes = 'B2'
        sheet.auto_filter.ref = sheet.dimensions
        widths = (14, 20, 20, 20, 20, 18, 16, 18, 16, 16, 14, 14, 12, 16, 16, 18, 16)
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[chr(64 + index) if index <= 26 else f'A{chr(64 + index - 26)}'].width = width

        timestamp = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y%m%d_%H%M%S')
        filename = f'section_wise_provision_stock_summary_{timestamp}.xlsx'
        workbook.save(os.path.join(cls.EXPORTS_DIR, filename))
        return filename

