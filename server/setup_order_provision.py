import random
from datetime import date
from sqlalchemy import text
from app import create_app
from app.extensions import db

def setup_db():
    app = create_app()
    with app.app_context():
        print("Creating table order_provision_summary_report_snapshot...")
        
        ddl_statements = [
            """
            DROP TABLE IF EXISTS order_provision_summary_report_snapshot CASCADE;
            """,
            """
            CREATE TABLE order_provision_summary_report_snapshot (
                po_number        VARCHAR(100) PRIMARY KEY,
                location         TEXT,
                party           TEXT,
                party_type      TEXT,
                division         TEXT,
                group_name       TEXT,
                classification   TEXT,
                section          TEXT,
                make            TEXT,
                purity           TEXT,
                master_collection TEXT,
                collection       TEXT,
                pieces           TEXT,
                gr_wt            TEXT,
                total            TEXT,
                business_head    TEXT,
                updated_at       TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_order_provision_snapshot_filters
            ON order_provision_summary_report_snapshot (
                division, group_name, purity, classification,
                make, collection, section, master_collection
            );
            """
        ]

        try:
            for statement in ddl_statements:
                db.session.execute(text(statement))
            db.session.commit()
            print("Table created successfully.")
        except Exception as e:
            print(f"Error creating table: {e}")
            db.session.rollback()
            return

        print("Seeding data...")
        
        locations = ['Mumbai', 'Rajkot', 'Surat', 'Dubai', 'Jaipur', 'Vapi', 'Chennai']
        parties = ['ABC Corp', 'XYZ Jewelers', 'Global Gems', 'Elite Gold', 'Diamond World', 'Jewel Art']
        party_types = ['Internal', 'External', 'Wholesale', 'Retail']
        divisions = ['Showroom', 'Boutique', 'Online', 'Wholesale', 'Export']
        groups = ['Bangles', 'Rings', 'Necklaces', 'Earrings', 'Pendants', 'Bracelets']
        classifications = ['Studded Jewelry', 'Gold Ornaments', 'Antique Collection', 'Modern Wear', 'Traditional']
        sections = ['Luxury', 'Daily Wear', 'Specialized', 'Classic', 'Premium']
        makes = ['Mumbai-Unit1', 'Rajkot-Workshop', 'Surat-Facility', 'In-House']
        purities = ['18KT', '22KT', '24KT', 'Platinum', '14KT']
        master_collections = ['Handmade', 'Machine Cut', 'Casting', 'Laser Engraved', 'Fusion']
        collections = ['Wedding 2024', 'Summer Breeze', 'Diwali Special', 'Corporate Chic', 'Bridal Saga']
        business_heads = ['Sandeep Shah', 'Amitabh Bachchan', 'Ratan Tata', 'Mukesh Ambani', 'Vikram Seth']

        sql_insert = text("""
            INSERT INTO order_provision_summary_report_snapshot (
                po_number, location, party, party_type, division, group_name, 
                classification, section, make, purity, master_collection, 
                collection, pieces, gr_wt, total, business_head
            ) VALUES (
                :po, :loc, :pty, :ptyp, :div, :grp, :cls, :sec, :mk, :pur, :mcol, :col, :pcs, :gwt, :tot, :bhead
            )
        """)

        for i in range(200):
            po_num = f"PO-{2024}-{1000 + i}"
            loc = random.choice(locations)
            pty = random.choice(parties)
            ptyp = random.choice(party_types)
            div = random.choice(divisions)
            grp = random.choice(groups)
            cls = random.choice(classifications)
            sec = random.choice(sections)
            mk = random.choice(makes)
            pur = random.choice(purities)
            mcol = random.choice(master_collections)
            col = random.choice(collections)
            
            pcs = str(random.randint(1, 50))
            gwt = f"{random.uniform(5.0, 500.0):.3f}"
            tot = f"{random.randint(10000, 500000)}"
            bhead = random.choice(business_heads)

            params = {
                'po': po_num, 'loc': loc, 'pty': pty, 'ptyp': ptyp,
                'div': div, 'grp': grp, 'cls': cls, 'sec': sec,
                'mk': mk, 'pur': pur, 'mcol': mcol, 'col': col,
                'pcs': pcs, 'gwt': gwt, 'tot': tot, 'bhead': bhead
            }

            try:
                db.session.execute(sql_insert, params)
            except Exception as ex:
                print(f"Error inserting row {i}: {ex}")
                db.session.rollback()

        db.session.commit()
        print("200 rows seeded successfully.")

if __name__ == "__main__":
    setup_db()
