import random
from datetime import date
from sqlalchemy import text
from app import create_app
from app.extensions import db

def setup_db():
    app = create_app()
    with app.app_context():
        print("Creating table order_status_report_snapshot...")
        
        # SQL provided by the user
        ddl_statements = [
            """
            DROP TABLE IF EXISTS order_status_report_snapshot CASCADE;
            """,
            """
            CREATE TABLE order_status_report_snapshot (
                snapshot_id        BIGSERIAL PRIMARY KEY,
                snapshot_date      DATE NOT NULL,
                division           VARCHAR(100),
                group_name         VARCHAR(100),
                purity             VARCHAR(50),
                classification     VARCHAR(150),
                make_location      VARCHAR(120),
                collection         VARCHAR(150),
                party_name         VARCHAR(200),
                
                make_owner            VARCHAR(100),
                collection_owner     VARCHAR(100),
                classification_owner VARCHAR(100),
                business_head        VARCHAR(100),

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

                dispatched_count   INTEGER NOT NULL DEFAULT 0,
                in_process_count   INTEGER NOT NULL DEFAULT 0,
                delayed_count      INTEGER NOT NULL DEFAULT 0,
                active_slots       INTEGER NOT NULL DEFAULT 0,

                sla_index_pct      NUMERIC(5,2),
                avg_quality_score  NUMERIC(3,2),
                fulfillment_pct    NUMERIC(5,2),

                updated_at         TIMESTAMP NOT NULL DEFAULT NOW(),

                hierarchy_key      TEXT GENERATED ALWAYS AS (
                    COALESCE(division,'') || '|' ||
                    COALESCE(group_name,'') || '|' ||
                    COALESCE(purity,'') || '|' ||
                    COALESCE(classification,'') || '|' ||
                    COALESCE(make_location,'') || '|' ||
                    COALESCE(collection,'') || '|' ||
                    COALESCE(party_name,'')
                ) STORED
            );
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_order_status_snapshot
            ON order_status_report_snapshot (snapshot_date, hierarchy_key);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_order_status_snapshot_filters
            ON order_status_report_snapshot (
                snapshot_date,
                division, group_name, purity, classification,
                make_location, collection, party_name,
                make_owner, collection_owner, classification_owner, business_head
            );
            """
        ]

        try:
            for statement in ddl_statements:
                db.session.execute(text(statement))
            db.session.commit()
            print("Table created successfully with new schema.")
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
        parties = ['ABC Corp', 'XYZ Jewelers', 'Global Gems', 'Elite Gold']
        
        make_owners = ['Rajesh Kumar', 'Anita Singh', 'Suresh Patel', 'Priya Sharma']
        coll_owners = ['Nitin Das', 'Meera Iyer', 'Arjun Kapoor', 'Sophie Chen']
        class_owners = ['Vikram Seth', 'Neha Gupta', 'Rahul Verma', 'Elena Rodriguez']
        business_heads = ['Sandeep Shah', 'Amitabh Bachchan', 'Ratan Tata', 'Mukesh Ambani']

        today = date.today()
        
        try:
            db.session.execute(text("TRUNCATE TABLE order_status_report_snapshot RESTART IDENTITY CASCADE"))
            db.session.commit()
        except Exception as e:
            print(f"Truncate failed: {e}")

        sql_insert = text("""
            INSERT INTO order_status_report_snapshot (
                snapshot_date, division, group_name, purity, classification, 
                make_location, collection, party_name,
                make_owner, collection_owner, classification_owner, business_head,
                a_completed_count, a_pending_count,
                b_completed_count, b_pending_count,
                c_completed_count, c_pending_count,
                d_completed_count, d_pending_count,
                e_completed_count, e_pending_count,
                f_completed_count, f_pending_count,
                g_completed_count, g_pending_count,
                total_count,
                dispatched_count, in_process_count, delayed_count, active_slots,
                sla_index_pct, avg_quality_score, fulfillment_pct
            ) VALUES (
                :date, :div, :grp, :pur, :cls, :loc, :col, :pty,
                :m_own, :c_own, :cl_own, :b_head,
                :ac, :ap, :bc, :bp, :cc, :cp, :dc, :dp, :ec, :ep, :fc, :fp, :gc, :gp,
                :total,
                :disp, :inp, :delayed, :slots,
                :sla, :qual, :full
            )
        """)

        for _ in range(200):
            div = random.choice(divisions)
            grp = random.choice(groups)
            pur = random.choice(purities)
            cls = random.choice(classifications)
            loc = random.choice(locations)
            col = random.choice(collections)
            pty = random.choice(parties)
            
            m_own = random.choice(make_owners)
            c_own = random.choice(coll_owners)
            cl_own = random.choice(class_owners)
            b_head = random.choice(business_heads)

            # Generate Completed/Pending pairs for each stage
            ac = random.randint(30, 200); ap = random.randint(10, 100)
            bc = random.randint(20, ac);  bp = random.randint(5, ap)
            cc = random.randint(15, bc);  cp = random.randint(2, bp)
            dc = random.randint(10, cc);  dp = random.randint(1, cp)
            ec = random.randint(5, dc);   ep = random.randint(0, dp)
            fc = random.randint(2, ec);   fp = random.randint(0, ep)
            gc = random.randint(0, fc);   gp = random.randint(0, fp)

            total = ac + ap

            params = {
                'date': today, 'div': div, 'grp': grp, 'pur': pur, 'cls': cls,
                'loc': loc, 'col': col, 'pty': pty,
                'm_own': m_own, 'c_own': c_own, 'cl_own': cl_own, 'b_head': b_head,
                'ac': ac, 'ap': ap, 'bc': bc, 'bp': bp, 'cc': cc, 'cp': cp,
                'dc': dc, 'dp': dp, 'ec': ec, 'ep': ep, 'fc': fc, 'fp': fp, 'gc': gc, 'gp': gp,
                'total': total,
                'disp': gc,
                'inp': total - gc,
                'delayed': random.randint(0, 15),
                'slots': random.randint(1, 30),
                'sla': round(random.uniform(85.0, 100.0), 2),
                'qual': round(random.uniform(4.0, 5.0), 2),
                'full': round(random.uniform(75.0, 100.0), 2)
            }

            try:
                db.session.execute(sql_insert, params)
            except Exception as ex:
                print(f"Skipping duplicate: {ex}")
                db.session.rollback()

        db.session.commit()
        print("200 rows seeded successfully.")

if __name__ == "__main__":
    setup_db()
