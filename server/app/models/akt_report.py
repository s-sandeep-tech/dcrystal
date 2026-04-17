from app.extensions import db
import os

class AKTTransactionPerformance(db.Model):
    __bind_key__ = 'akt_db'
    __tablename__ = 'akt_dhanteras_saledetails'
    
    # Only use 'muziris' schema in production where it exists
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('ENABLE_AKT_DB') == 'true':
        __table_args__ = {'schema': 'muziris'}
    else:
        __table_args__ = {}

    # Updated to lowercase as per PostgreSQL table definition
    year = db.Column(db.Integer)
    date = db.Column(db.Date)
    country = db.Column(db.String(100))
    subledger = db.Column(db.String(100))
    region = db.Column(db.String(100))
    state = db.Column(db.String(100))
    location = db.Column(db.String(100))
    divisionname = db.Column(db.String(100))
    timepartt = db.Column(db.Integer, primary_key=True)
    billcount = db.Column(db.Integer)
    grossweight = db.Column(db.Numeric(18, 4))
    stoneweight = db.Column(db.Numeric(18, 4))
    diamondcarat = db.Column(db.Numeric(18, 4))
    colourstonecarat = db.Column(db.Numeric(18, 4))
    netweight = db.Column(db.Numeric(18, 4))
    metalvalue = db.Column(db.Numeric(18, 4))
    netstonevalue = db.Column(db.Numeric(18, 4))
    netdiamondvalue = db.Column(db.Numeric(18, 4))
    netcolourstonevalue = db.Column(db.Numeric(18, 4))
    netmcvalue = db.Column(db.Numeric(18, 4))
    invoiceamt = db.Column(db.Numeric(18, 4))
    mcprofit = db.Column(db.Numeric(18, 4))
    stonevalueprofit = db.Column(db.Numeric(18, 4))
    turnover = db.Column(db.Numeric(18, 4))
    tsk = db.Column(db.String(100))
    hourlybillcount = db.Column(db.Integer)
    perminutebillcount = db.Column(db.Numeric(18, 4))
    billtime = db.Column(db.String(20), primary_key=True)
    country_actual = db.Column(db.String(100), primary_key=True)

    def to_dict(self):
        return {
            "year": self.year,
            "date": str(self.date) if self.date else None,
            "country": self.country,
            "subledger": self.subledger,
            "region": self.region,
            "state": self.state,
            "location": self.location,
            "divisionname": self.divisionname,
            "timepartt": self.timepartt,
            "billcount": self.billcount,
            "grossweight": float(self.grossweight) if self.grossweight else 0,
            "stoneweight": float(self.stoneweight) if self.stoneweight else 0,
            "diamondcarat": float(self.diamondcarat) if self.diamondcarat else 0,
            "colourstonecarat": float(self.colourstonecarat) if self.colourstonecarat else 0,
            "netweight": float(self.netweight) if self.netweight else 0,
            "metalvalue": float(self.metalvalue) if self.metalvalue else 0,
            "netstonevalue": float(self.netstonevalue) if self.netstonevalue else 0,
            "netdiamondvalue": float(self.netdiamondvalue) if self.netdiamondvalue else 0,
            "netcolourstonevalue": float(self.netcolourstonevalue) if self.netcolourstonevalue else 0,
            "netmcvalue": float(self.netmcvalue) if self.netmcvalue else 0,
            "invoiceamt": float(self.invoiceamt) if self.invoiceamt else 0,
            "mcprofit": float(self.mcprofit) if self.mcprofit else 0,
            "stonevalueprofit": float(self.stonevalueprofit) if self.stonevalueprofit else 0,
            "turnover": float(self.turnover) if self.turnover else 0,
            "tsk": self.tsk,
            "hourlybillcount": self.hourlybillcount,
            "perminutebillcount": float(self.perminutebillcount) if self.perminutebillcount else 0,
            "billtime": self.billtime,
            "country_actual": self.country_actual
        }
