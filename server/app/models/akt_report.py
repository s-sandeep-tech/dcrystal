from app.extensions import db
import os
from sqlalchemy import Column, Integer, String, Numeric, Date, Time, DateTime

class AKTTransactionPerformance(db.Model):
    __bind_key__ = 'akt_db'
    __tablename__ = 'akt_dhanteras_saledetails'
    
    # Only use 'muziris' schema in production where it exists
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('ENABLE_AKT_DB') == 'true':
        __table_args__ = {'schema': 'muziris'}
    else:
        __table_args__ = {}

    # Exact Schema Alignment as per PostgreSQL definition
    year = db.Column(db.Integer)
    date = db.Column(db.DateTime)  # timestamp without time zone
    country = db.Column(db.String(255))
    subledger = db.Column(db.String(255))
    region = db.Column(db.String(255))
    state = db.Column(db.String(255))
    location = db.Column(db.String(255))
    divisionname = db.Column(db.String(255))
    timepartt = db.Column(db.Integer, primary_key=True)
    billcount = db.Column(db.Integer)
    grossweight = db.Column(db.Numeric)
    stoneweight = db.Column(db.Numeric)
    diamondcarat = db.Column(db.Numeric)
    colourstonecarat = db.Column(db.Numeric)
    netweight = db.Column(db.Numeric)
    metalvalue = db.Column(db.Numeric)
    netstonevalue = db.Column(db.Numeric)
    netdiamondvalue = db.Column(db.Numeric)
    netcolourstonevalue = db.Column(db.Numeric)
    netmcvalue = db.Column(db.Numeric)
    invoiceamt = db.Column(db.Numeric)
    mcprofit = db.Column(db.Numeric)
    stonevalueprofit = db.Column(db.Numeric)
    turnover = db.Column(db.Numeric)
    tsk = db.Column(db.Numeric)
    hourlybillcount = db.Column(db.Integer)
    perminutebillcount = db.Column(db.String(255)) # Only this metric is VARCHAR in DB
    billtime = db.Column(db.Time, primary_key=True) # time without time zone
    country_actual = db.Column(db.String(255), primary_key=True)

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
            "tsk": float(self.tsk) if self.tsk else 0,
            "hourlybillcount": self.hourlybillcount,
            "perminutebillcount": self.perminutebillcount,
            "billtime": str(self.billtime) if self.billtime else None,
            "country_actual": self.country_actual
        }
