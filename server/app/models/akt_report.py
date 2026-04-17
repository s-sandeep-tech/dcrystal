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

    # Map all columns as String as they are character varying in the DB
    year = db.Column(db.String(100))
    date = db.Column(db.Date)
    country = db.Column(db.String(100))
    subledger = db.Column(db.String(100))
    region = db.Column(db.String(100))
    state = db.Column(db.String(100))
    location = db.Column(db.String(100))
    divisionname = db.Column(db.String(100))
    timepartt = db.Column(db.String(100), primary_key=True)
    billcount = db.Column(db.String(100))
    grossweight = db.Column(db.String(100))
    stoneweight = db.Column(db.String(100))
    diamondcarat = db.Column(db.String(100))
    colourstonecarat = db.Column(db.String(100))
    netweight = db.Column(db.String(100))
    metalvalue = db.Column(db.String(100))
    netstonevalue = db.Column(db.String(100))
    netdiamondvalue = db.Column(db.String(100))
    netcolourstonevalue = db.Column(db.String(100))
    netmcvalue = db.Column(db.String(100))
    invoiceamt = db.Column(db.String(100))
    mcprofit = db.Column(db.String(100))
    stonevalueprofit = db.Column(db.String(100))
    turnover = db.Column(db.String(100))
    tsk = db.Column(db.String(100))
    hourlybillcount = db.Column(db.String(100))
    perminutebillcount = db.Column(db.String(100))
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
            "grossweight": self.grossweight,
            "stoneweight": self.stoneweight,
            "diamondcarat": self.diamondcarat,
            "colourstonecarat": self.colourstonecarat,
            "netweight": self.netweight,
            "metalvalue": self.metalvalue,
            "netstonevalue": self.netstonevalue,
            "netdiamondvalue": self.netdiamondvalue,
            "netcolourstonevalue": self.netcolourstonevalue,
            "netmcvalue": self.netmcvalue,
            "invoiceamt": self.invoiceamt,
            "mcprofit": self.mcprofit,
            "stonevalueprofit": self.stonevalueprofit,
            "turnover": self.turnover,
            "tsk": self.tsk,
            "hourlybillcount": self.hourlybillcount,
            "perminutebillcount": self.perminutebillcount,
            "billtime": self.billtime,
            "country_actual": self.country_actual
        }
