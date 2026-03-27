import os
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

# IST timezone offset
IST = timezone(timedelta(hours=5, minutes=30))

# Directory where exports are saved
if os.path.isdir('/app/uploads'):
    EXPORTS_DIR = '/app/uploads/exports'
else:
    # Fallback for local development outside docker
    EXPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', 'exports')


def _ensure_exports_dir():
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def _safe_float(val):
    try:
        if val is None:
            return 0.0
        return float(val)
    except Exception:
        return 0.0


def _safe_int(val):
    try:
        if val is None:
            return 0
        return int(float(val))
    except Exception:
        return 0


def generate_outstanding_po_export(filters: dict) -> str:
    """
    Query OutstandingPurchaseOrderStatusSnapshot with the given filters,
    write a formatted .xlsx file to EXPORTS_DIR, and return the filename.
    """
    try:
        import openpyxl
        from openpyxl.styles import (
            Font, PatternFill, Alignment, Border, Side, numbers
        )
        from openpyxl.utils import get_column_letter
    except ImportError as e:
        raise RuntimeError(f"openpyxl not installed: {e}")

    from app.extensions import db
    from app.models import OutstandingPurchaseOrderStatusSnapshot
    from sqlalchemy import func

    _ensure_exports_dir()

    # ── 1. Build Query ────────────────────────────────────────────────────────
    search              = filters.get('search', '').strip()
    classification_owner = filters.get('classification_owner', '')
    make_owner          = filters.get('make_owner', '')
    collection_owner    = filters.get('collection_owner', '')
    purchase_ro         = filters.get('purchase_ro', '')
    party               = filters.get('party', '')
    classification      = filters.get('classification', '')
    make                = filters.get('make', '')
    collection          = filters.get('collection', '')
    section             = filters.get('section', '')
    division            = filters.get('division', '')
    group               = filters.get('group', '')
    purity              = filters.get('purity', '')
    age_min             = filters.get('age_min')
    age_max             = filters.get('age_max')
    exclude_receipt     = filters.get('exclude_receipt', False)

    if isinstance(age_min, str) and age_min.strip():
        try: age_min = int(age_min)
        except Exception: age_min = None
    if isinstance(age_max, str) and age_max.strip():
        try: age_max = int(age_max)
        except Exception: age_max = None
    if isinstance(exclude_receipt, str):
        exclude_receipt = exclude_receipt.lower() == 'true'

    q = db.session.query(OutstandingPurchaseOrderStatusSnapshot)
    if search:
        q = q.filter(
            OutstandingPurchaseOrderStatusSnapshot.classification_owner.ilike(f'%{search}%') |
            OutstandingPurchaseOrderStatusSnapshot.make_owner.ilike(f'%{search}%') |
            OutstandingPurchaseOrderStatusSnapshot.collection_owner.ilike(f'%{search}%') |
            OutstandingPurchaseOrderStatusSnapshot.party.ilike(f'%{search}%') |
            OutstandingPurchaseOrderStatusSnapshot.order_number.ilike(f'%{search}%')
        )
    if classification_owner:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.classification_owner == classification_owner)
    if make_owner:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.make_owner == make_owner)
    if collection_owner:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.collection_owner == collection_owner)
    if purchase_ro:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.purchase_ro == purchase_ro)
    if party:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.party == party)
    if classification:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.classification == classification)
    if make:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.make == make)
    if collection:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.collection == collection)
    if section:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.section == section)
    if division:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.division == division)
    if group:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.group == group)
    if purity:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.purity == purity)
    if age_min is not None:
        q = q.filter(func.current_date() - OutstandingPurchaseOrderStatusSnapshot.order_date >= age_min)
    if age_max is not None:
        q = q.filter(func.current_date() - OutstandingPurchaseOrderStatusSnapshot.order_date <= age_max)
    if exclude_receipt:
        q = q.filter(OutstandingPurchaseOrderStatusSnapshot.receipt_present != 'Y')

    rows = q.order_by(
        OutstandingPurchaseOrderStatusSnapshot.classification_owner,
        OutstandingPurchaseOrderStatusSnapshot.make_owner,
        OutstandingPurchaseOrderStatusSnapshot.collection_owner,
        OutstandingPurchaseOrderStatusSnapshot.order_date
    ).all()

    # ── 2. Build Active Filter Summary ────────────────────────────────────────
    active_filters = []
    if search:              active_filters.append(('Search', search))
    if classification_owner: active_filters.append(('Classification Owner', classification_owner))
    if make_owner:          active_filters.append(('Make Owner', make_owner))
    if collection_owner:    active_filters.append(('Collection Owner', collection_owner))
    if purchase_ro:         active_filters.append(('Purchase RO', purchase_ro))
    if party:               active_filters.append(('Party', party))
    if classification:      active_filters.append(('Classification', classification))
    if make:                active_filters.append(('Make', make))
    if collection:          active_filters.append(('Collection', collection))
    if section:             active_filters.append(('Section', section))
    if division:            active_filters.append(('Division', division))
    if group:               active_filters.append(('Group', group))
    if purity:              active_filters.append(('Purity', purity))
    if age_min is not None: active_filters.append(('Min Age (Days)', str(age_min)))
    if age_max is not None: active_filters.append(('Max Age (Days)', str(age_max)))
    if exclude_receipt:     active_filters.append(('Exclude Receipt', 'Yes'))
    if not active_filters:
        active_filters.append(('Filters', 'None — showing all data'))

    # ── 3. Create Workbook ────────────────────────────────────────────────────
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Outstanding Purchase Orders'

    # ── Colour Palette ────────────────────────────────────────────────────────
    PRIMARY_FILL   = PatternFill('solid', fgColor='1E3A5F')   # Dark navy
    HEADER_FILL    = PatternFill('solid', fgColor='2563EB')   # Blue
    FILTER_FILL    = PatternFill('solid', fgColor='EFF6FF')   # Light blue tint
    FOOTER_FILL    = PatternFill('solid', fgColor='F1F5F9')   # Light gray
    ALT_FILL       = PatternFill('solid', fgColor='F8FAFC')   # Very light gray for alt rows

    TITLE_FONT     = Font(name='Calibri', bold=True, size=14, color='FFFFFF')
    SUB_FONT       = Font(name='Calibri', size=10, color='94A3B8', italic=True)
    HEADER_FONT    = Font(name='Calibri', bold=True, size=9, color='FFFFFF')
    FILTER_KEY_F   = Font(name='Calibri', bold=True, size=9, color='1E40AF')
    FILTER_VAL_F   = Font(name='Calibri', size=9, color='1E3A5F')
    DATA_FONT      = Font(name='Calibri', size=9, color='1E293B')
    FOOTER_FONT    = Font(name='Calibri', bold=True, size=9, color='1E293B')
    SECTION_FONT   = Font(name='Calibri', bold=True, size=9, color='64748B')

    THIN_BORDER = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # Number formats
    NUM_FMT_3DP = '#,##0.000'
    NUM_FMT_INT = '#,##0'
    NUM_FMT_DATE = 'DD-MMM-YYYY'

    # Total columns in the sheet
    TOTAL_COLS = 20

    # ── Row 1: Report Title ───────────────────────────────────────────────────
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=TOTAL_COLS)
    title_cell = ws.cell(row=1, column=1,
                         value='Outstanding Purchase Order Status Report')
    title_cell.font = TITLE_FONT
    title_cell.fill = PRIMARY_FILL
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    # ── Row 2: Generated timestamp ────────────────────────────────────────────
    now_ist = datetime.now(IST)
    gen_time_str = now_ist.strftime('%d %b %Y, %I:%M %p IST')
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=TOTAL_COLS)
    gen_cell = ws.cell(row=2, column=1, value=f'Generated: {gen_time_str}   |   Total Records: {len(rows)}')
    gen_cell.font = Font(name='Calibri', size=9, color='64748B')
    gen_cell.fill = PatternFill('solid', fgColor='F8FAFC')
    gen_cell.alignment = Alignment(horizontal='right', vertical='center')
    ws.row_dimensions[2].height = 18

    # ── Row 3: Blank separator ────────────────────────────────────────────────
    cur_row = 3

    # ── Filter Criteria Section ───────────────────────────────────────────────
    # Section header
    ws.merge_cells(start_row=cur_row, start_column=1, end_row=cur_row, end_column=TOTAL_COLS)
    sec_cell = ws.cell(row=cur_row, column=1, value='  APPLIED FILTERS')
    sec_cell.font = SECTION_FONT
    sec_cell.fill = PatternFill('solid', fgColor='E2E8F0')
    sec_cell.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[cur_row].height = 16
    cur_row += 1

    # Filter rows: 2 filters per row (col 1-2, col 3-4, etc.)
    for i in range(0, len(active_filters), 3):
        for j in range(3):
            if i + j < len(active_filters):
                label, value = active_filters[i + j]
                base = j * 4 + 1  # col 1, 5, 9
                lbl_cell = ws.cell(row=cur_row, column=base, value=label)
                lbl_cell.font = FILTER_KEY_F
                lbl_cell.fill = FILTER_FILL
                lbl_cell.alignment = Alignment(horizontal='right', vertical='center')
                lbl_cell.border = THIN_BORDER
                ws.merge_cells(start_row=cur_row, start_column=base, end_row=cur_row, end_column=base)

                val_cell = ws.cell(row=cur_row, column=base + 1, value=value)
                val_cell.font = FILTER_VAL_F
                val_cell.fill = FILTER_FILL
                val_cell.alignment = Alignment(horizontal='left', vertical='center')
                val_cell.border = THIN_BORDER
                ws.merge_cells(start_row=cur_row, start_column=base + 1, end_row=cur_row, end_column=base + 3)
        ws.row_dimensions[cur_row].height = 16
        cur_row += 1

    # Blank separator before data
    cur_row += 1

    # ── Data Headers ──────────────────────────────────────────────────────────
    COLUMNS = [
        # (header_label, column_key, width, number_format, alignment)
        ('Order Number',          'order_number',          20, None,         'left'),
        ('Order Date',            'order_date',            14, NUM_FMT_DATE, 'center'),
        ('Age (Days)',            'age_days',              10, NUM_FMT_INT,  'right'),
        ('Party',                 'party',                 25, None,         'left'),
        ('Classification Owner',  'classification_owner',  22, None,         'left'),
        ('Make Owner',            'make_owner',            22, None,         'left'),
        ('Collection Owner',      'collection_owner',      22, None,         'left'),
        ('Purchase RO',           'purchase_ro',           16, None,         'left'),
        ('Classification',        'classification',        18, None,         'left'),
        ('Make',                  'make',                  18, None,         'left'),
        ('Collection',            'collection',            18, None,         'left'),
        ('Section',               'section',               14, None,         'left'),
        ('Division',              'division',              14, None,         'left'),
        ('Group',                 'group',                 14, None,         'left'),
        ('Purity',                'purity',                12, None,         'center'),
        ('Receipt',               'receipt_present',       10, None,         'center'),
        ('Order Pcs',             'order_pieces',          12, NUM_FMT_INT,  'right'),
        ('Order Wt (g)',          'order_weight',          14, NUM_FMT_3DP,  'right'),
        ('Accepted Pcs',          'accepted_pieces',       12, NUM_FMT_INT,  'right'),
        ('Accepted Wt (g)',       'accepted_weight',       14, NUM_FMT_3DP,  'right'),
    ]

    header_row = cur_row
    for col_idx, (label, _, width, _, align) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=label)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[header_row].height = 30

    # Enable auto-filter on data
    ws.auto_filter.ref = (
        f"A{header_row}:{get_column_letter(len(COLUMNS))}{header_row + len(rows)}"
    )
    ws.freeze_panes = f'A{header_row + 1}'

    # ── Data Rows ─────────────────────────────────────────────────────────────
    today = datetime.now(IST).date()

    # Totals accumulators
    total_order_pcs = 0
    total_order_wt = 0.0
    total_accepted_pcs = 0
    total_accepted_wt = 0.0

    for row_idx, record in enumerate(rows, start=1):
        xls_row = header_row + row_idx
        alt = (row_idx % 2 == 0)
        row_fill = ALT_FILL if alt else None

        # Pre-compute age
        if record.order_date:
            age_days = (today - record.order_date).days
        else:
            age_days = None

        order_pcs = _safe_int(record.order_pieces)
        order_wt  = _safe_float(record.order_weight)
        acc_pcs   = _safe_int(record.accepted_pieces)
        acc_wt    = _safe_float(record.accepted_weight)

        total_order_pcs   += order_pcs
        total_order_wt    += order_wt
        total_accepted_pcs += acc_pcs
        total_accepted_wt  += acc_wt

        row_values = [
            record.order_number or '',
            record.order_date,           # date object → openpyxl will format it
            age_days,
            record.party or '',
            record.classification_owner or '',
            record.make_owner or '',
            record.collection_owner or '',
            record.purchase_ro or '',
            record.classification or '',
            record.make or '',
            record.collection or '',
            record.section or '',
            record.division or '',
            record.group or '',
            record.purity or '',
            record.receipt_present or '',
            order_pcs,
            order_wt,
            acc_pcs,
            acc_wt,
        ]

        for col_idx, (_, _, _, num_fmt, align) in enumerate(COLUMNS, start=1):
            cell = ws.cell(row=xls_row, column=col_idx, value=row_values[col_idx - 1])
            cell.font = DATA_FONT
            cell.alignment = Alignment(horizontal=align, vertical='center')
            cell.border = THIN_BORDER
            if row_fill:
                cell.fill = row_fill
            if num_fmt:
                cell.number_format = num_fmt

        ws.row_dimensions[xls_row].height = 15

    # ── Footer Totals Row ─────────────────────────────────────────────────────
    footer_row = header_row + len(rows) + 1
    footer_values = {
        1: 'TOTALS',
        17: total_order_pcs,
        18: total_order_wt,
        19: total_accepted_pcs,
        20: total_accepted_wt,
    }
    for col_idx in range(1, len(COLUMNS) + 1):
        cell = ws.cell(row=footer_row, column=col_idx,
                       value=footer_values.get(col_idx, ''))
        cell.font = FOOTER_FONT
        cell.fill = FOOTER_FILL
        cell.border = THIN_BORDER
        if col_idx == 1:
            cell.alignment = Alignment(horizontal='left', vertical='center')
        elif col_idx in (17, 19):
            cell.number_format = NUM_FMT_INT
            cell.alignment = Alignment(horizontal='right', vertical='center')
        elif col_idx in (18, 20):
            cell.number_format = NUM_FMT_3DP
            cell.alignment = Alignment(horizontal='right', vertical='center')
    ws.row_dimensions[footer_row].height = 18

    # ── Save ──────────────────────────────────────────────────────────────────
    timestamp = now_ist.strftime('%Y%m%d_%H%M%S')
    filename = f'outstanding_po_export_{timestamp}.xlsx'
    filepath = os.path.join(EXPORTS_DIR, filename)
    wb.save(filepath)

    logger.info(f'Export saved: {filepath}  ({len(rows)} records)')
    return filename


def generate_pending_acceptance_export(filters: dict) -> str:
    """
    Query PendingAcceptanceAction with filters, explode action_data (specifically CANCEL actions),
    and write to an .xlsx file.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError as e:
        raise RuntimeError(f"openpyxl not installed: {e}")

    from app.extensions import db
    from app.models.snapshots import PendingAcceptanceAction
    from sqlalchemy import func

    _ensure_exports_dir()

    # ── 1. Build Query ────────────────────────────────────────────────────────
    status_filter = filters.get('status_filter', 'pending_to_deliver_not_barcoded')
    collection_owner = filters.get('collection_owner', '')
    make_owner = filters.get('make_owner', '')
    supplier = filters.get('supplier', '')
    collection = filters.get('collection', '')
    action_type = filters.get('action_action_type', '')  # Optional: filter by action type (e.g. CANCEL)

    q = db.session.query(PendingAcceptanceAction)
    
    if status_filter:
        q = q.filter(PendingAcceptanceAction.status_filter == status_filter)
    if collection_owner:
        q = q.filter(PendingAcceptanceAction.collection_owner == collection_owner)
    if make_owner:
        q = q.filter(PendingAcceptanceAction.make_owner == make_owner)
    if supplier:
        q = q.filter(PendingAcceptanceAction.supplier == supplier)
    if collection:
        q = q.filter(PendingAcceptanceAction.collection == collection)
    if action_type:
        q = q.filter(PendingAcceptanceAction.action_type == action_type)

    actions = q.order_by(PendingAcceptanceAction.created_at.desc()).all()

    # ── 2. Explode Data ───────────────────────────────────────────────────────
    # We flatten the action_data (JSON) into individual rows per PO
    po_rows = []
    for action in actions:
        data = action.action_data
        if not data:
            continue
            
        items_to_process = []
        schedules_str = ""
        
        if isinstance(data, list):
            # Old format or simple CANCEL action
            items_to_process = data
        elif isinstance(data, dict):
            # New structure with schedules and unselected_pos for CONTINUE
            if action.action_type == 'CONTINUE':
                items_to_process = data.get('unselected_pos', [])
                schedules = data.get('schedules', [])
                # Format: "Weight (Date), Weight (Date)..."
                schedules_str = ", ".join([f"{s.get('weight')} ({s.get('delivery_date')})" for s in schedules])
            elif action.action_type == 'CANCEL':
                # Handle possible future object-based CANCEL
                items_to_process = data.get('selected', []) + data.get('unselected', [])

        for item in items_to_process:
            # item is a dict like {'po_number': '...', 'po_date': '...', 'total_weight': ..., 'order_piece': ..., 'vendor': '...'}
            po_num = item.get('po_number') or item.get('order_number')
            if not po_num:
                continue
                
            po_rows.append({
                'action_id': action.id,
                'action_type': action.action_type,
                'action_date': action.created_at.strftime('%Y-%m-%d %H:%M') if action.created_at else '',
                'username': action.username or '',
                'reason': action.reason or '',
                'collection_owner': action.collection_owner or '',
                'make_owner': action.make_owner or '',
                'supplier': action.supplier or '',
                'collection': action.collection or '',
                'status_filter': action.status_filter or '',
                'po_number': po_num,
                'po_date': item.get('po_date') or item.get('order_date') or '',
                'order_weight': item.get('total_weight') or item.get('order_weight') or 0.0,
                'order_piece': item.get('order_piece') or 0,
                'schedules': schedules_str
            })

    # ── 3. Create Workbook ────────────────────────────────────────────────────
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Pending Acceptance Actions'

    # Styles
    PRIMARY_FILL = PatternFill('solid', fgColor='1E3A5F')
    HEADER_FILL = PatternFill('solid', fgColor='2563EB')
    ALT_FILL = PatternFill('solid', fgColor='F8FAFC')
    
    TITLE_FONT = Font(name='Calibri', bold=True, size=14, color='FFFFFF')
    HEADER_FONT = Font(name='Calibri', bold=True, size=9, color='FFFFFF')
    DATA_FONT = Font(name='Calibri', size=9, color='1E293B')
    
    THIN_BORDER = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    COLUMNS = [
        ('Action ID',    10, 'center'),
        ('Action Type',  12, 'center'),
        ('Action Date',  18, 'center'),
        ('Username',     18, 'left'),
        ('Reason',       30, 'left'),
        ('Coll. Owner',  20, 'left'),
        ('Make Owner',   20, 'left'),
        ('Supplier',     25, 'left'),
        ('Collection',   20, 'left'),
        ('PO Number',    18, 'left'),
        ('PO Date',      15, 'center'),
        ('PO Weight',    14, 'right'),
        ('PO Pieces',    12, 'right'),
        ('Schedules (Fulfillment)', 40, 'left')
    ]

    TOTAL_COLS = len(COLUMNS)

    # Title
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=TOTAL_COLS)
    title_cell = ws.cell(row=1, column=1, value='Pending Acceptance Feedback Action Details Export')
    title_cell.font = TITLE_FONT
    title_cell.fill = PRIMARY_FILL
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    # Headers
    for col_idx, (label, width, align) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=2, column=col_idx, value=label)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[2].height = 20

    # Data
    for row_idx, row_data in enumerate(po_rows, start=3):
        values = [
            row_data['action_id'],
            row_data['action_type'],
            row_data['action_date'],
            row_data['username'],
            row_data['reason'],
            row_data['collection_owner'],
            row_data['make_owner'],
            row_data['supplier'],
            row_data['collection'],
            row_data['po_number'],
            row_data['po_date'],
            row_data['order_weight'],
            row_data['order_piece'],
            row_data['schedules']
        ]
        alt = (row_idx % 2 == 0)
        for col_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = DATA_FONT
            cell.alignment = Alignment(horizontal=COLUMNS[col_idx-1][2], vertical='center')
            cell.border = THIN_BORDER
            if alt:
                cell.fill = ALT_FILL
            
            # Number formatting
            if col_idx == 12: # Weight
                cell.number_format = '#,##0.000'
            elif col_idx == 13: # Piece
                cell.number_format = '#,##0'

    # Save
    now_ist = datetime.now(IST)
    timestamp = now_ist.strftime('%Y%m%d_%H%M%S')
    filename = f'pending_acceptance_export_{timestamp}.xlsx'
    filepath = os.path.join(EXPORTS_DIR, filename)
    wb.save(filepath)

    logger.info(f'Export saved: {filepath} ({len(po_rows)} records)')
    return filename
