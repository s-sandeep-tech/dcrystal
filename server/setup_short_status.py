import random
from datetime import date
from sqlalchemy import text, Numeric
from app import create_app
from app.extensions import db

def setup_db():
    app = create_app()
    with app.app_context():
        print("Creating table short_status_report_snapshot...")
        
        ddl_statements = [
            """
            DROP TABLE IF EXISTS short_status_report_snapshot CASCADE;
            """,
            """
            CREATE TABLE short_status_report_snapshot (
                snapshot_id        BIGSERIAL PRIMARY KEY,
                snapshot_date      DATE NOT NULL,
                division           VARCHAR(100),
                group_name         VARCHAR(100),
                purity             VARCHAR(50),
                classification     VARCHAR(150),
                make_location      VARCHAR(120),
                collection         VARCHAR(150),
                section            VARCHAR(100),
                product_type       VARCHAR(100),
                weight             NUMERIC(10, 3),
                
                a_completed_count  INTEGER NOT NULL DEFAULT 0,
                a_pending_count    INTEGER NOT NULL DEFAULT 0,
                b_completed_count  INTEGER NOT NULL DEFAULT 0,
                b_pending_count    INTEGER NOT NULL DEFAULT 0,
                c_completed_count  INTEGER NOT NULL DEFAULT 0,
                c_pending_count    INTEGER NOT NULL DEFAULT 0,
                d_completed_count  INTEGER NOT NULL DEFAULT 0,
                d_pending_count    INTEGER NOT NULL DEFAULT 0,
                e_completed_count  INTEGER NOT NULL DEFAULT 0,
                e_pending_count    INTEGER NOT NULL DEFAULT 0,
                f_completed_count  INTEGER NOT NULL DEFAULT 0,
                f_pending_count    INTEGER NOT NULL DEFAULT 0,
                g_completed_count  INTEGER NOT NULL DEFAULT 0,
                g_pending_count    INTEGER NOT NULL DEFAULT 0,

                total_count        INTEGER NOT NULL DEFAULT 0,
                updated_at         TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_short_status_snapshot_filters
            ON short_status_report_snapshot (
                snapshot_date,
                division, group_name, purity, classification,
                make_location, collection, section, product_type
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
        
        divisions = ['Showroom', 'Boutique', 'Online', 'Wholesale']
        groups = ['Bangles', 'Rings', 'Necklaces', 'Earrings', 'Pendants']
        purities = ['18KT', '22KT', '24KT', 'Platinum']
        classifications = ['Studded Jewelry', 'Gold Ornaments', 'Antique Collection', 'Modern Wear']
        locations = ['Mumbai', 'Rajkot', 'Surat', 'Dubai', 'Jaipur']
        collections = ['Wedding 2024', 'Summer Breeze', 'Diwali Special', 'Corporate Chic']
        sections = ['Luxury', 'Daily Wear', 'Specialized', 'Classic']
        types = ['Handmade', 'Machine Cut', 'Casting', 'Laser Engraved']

        today = date.today()
        
        sql_insert = text("""
            INSERT INTO short_status_report_snapshot (
                snapshot_date, division, group_name, purity, classification, 
                make_location, collection, section, product_type, weight,
                a_completed_count, a_pending_count,
                b_completed_count, b_pending_count,
                c_completed_count, c_pending_count,
                d_completed_count, d_pending_count,
                e_completed_count, e_pending_count,
                f_completed_count, f_pending_count,
                g_completed_count, g_pending_count,
                total_count
            ) VALUES (
                :date, :div, :grp, :pur, :cls, :loc, :col, :sec, :typ, :wgt,
                :ac, :ap, :bc, :bp, :cc, :cp, :dc, :dp, :ec, :ep, :fc, :fp, :gc, :gp,
                :total
            )
        """)

        for _ in range(200):
            div = random.choice(divisions)
            grp = random.choice(groups)
            pur = random.choice(purities)
            cls = random.choice(classifications)
            loc = random.choice(locations)
            col = random.choice(collections)
            sec = random.choice(sections)
            typ = random.choice(types)
            wgt = round(random.uniform(2.0, 150.0), 3)

            ac = random.randint(10, 50); ap = random.randint(2, 20)
            bc = random.randint(5, ac);  bp = random.randint(1, ap)
            cc = random.randint(2, bc);  cp = random.randint(0, bp)
            dc = random.randint(1, cc);  dp = random.randint(0, cp)
            ec = random.randint(0, dc);  ep = random.randint(0, dp)
            fc = random.randint(0, ec);  fp = random.randint(0, ep)
            gc = random.randint(0, fc);  gp = random.randint(0, fp)

            total = ac + ap

            params = {
                'date': today, 'div': div, 'grp': grp, 'pur': pur, 'cls': cls,
                'loc': loc, 'col': col, 'sec': sec, 'typ': typ, 'wgt': wgt,
                'ac': ac, 'ap': ap, 'bc': bc, 'bp': bp, 'cc': cc, 'cp': cp,
                'dc': dc, 'dp': dp, 'ec': ec, 'ep': ep, 'fc': fc, 'fp': fp, 'gc': gc, 'gp': gp,
                'total': total
            }

            db.session.execute(sql_insert, params)

        db.session.commit()
        print("200 rows seeded successfully.")

if __name__ == "__main__":
    setup_db()
