from app.extensions import db

class AKTTransactionPerformance(db.Model):
    __bind_key__ = 'akt_db'
    __tablename__ = 'akt_dhanteras_saledetails'
    __table_args__ = {'schema': 'muziris'}

    # Since it's a report table, we might not have a clear PK, 
    # but SQLAlchemy needs one. I'll use a combination or add an id if possible.
    # If it's read-only, we can just pick some columns.
    Year = db.Column(db.Integer)
    Date = db.Column(db.Date)
    Country = db.Column(db.String(100))
    Subledger = db.Column(db.String(100))
    Region = db.Column(db.String(100))
    State = db.Column(db.String(100))
    Location = db.Column(db.String(100))
    DivisionName = db.Column(db.String(100))
    TimePartt = db.Column(db.Integer, primary_key=True) # Assuming this as part of PK for simplicity if no other
    BillCount = db.Column(db.Integer)
    GrossWeight = db.Column(db.Numeric(18, 4))
    StoneWeight = db.Column(db.Numeric(18, 4))
    DiamondCarat = db.Column(db.Numeric(18, 4))
    ColourStoneCarat = db.Column(db.Numeric(18, 4))
    NetWeight = db.Column(db.Numeric(18, 4))
    MetalValue = db.Column(db.Numeric(18, 4))
    NetStoneValue = db.Column(db.Numeric(18, 4))
    NetDiamondValue = db.Column(db.Numeric(18, 4))
    NetColourStoneValue = db.Column(db.Numeric(18, 4))
    NetMCValue = db.Column(db.Numeric(18, 4))
    InvoiceAmt = db.Column(db.Numeric(18, 4))
    MCprofit = db.Column(db.Numeric(18, 4))
    StoneVAlueProfit = db.Column(db.Numeric(18, 4))
    Turnover = db.Column(db.Numeric(18, 4))
    TSK = db.Column(db.String(100))
    HourlyBillCount = db.Column(db.Integer)
    PerMinuteBillCount = db.Column(db.Numeric(18, 4))
    BillTime = db.Column(db.String(20), primary_key=True) # Adding another to reduce collisions
    Country_Actual = db.Column(db.String(100), primary_key=True)

    def to_dict(self):
        return {
            "Year": self.Year,
            "Date": str(self.Date) if self.Date else None,
            "Country": self.Country,
            "Subledger": self.Subledger,
            "Region": self.Region,
            "State": self.State,
            "Location": self.Location,
            "DivisionName": self.DivisionName,
            "TimePartt": self.TimePartt,
            "BillCount": self.BillCount,
            "GrossWeight": float(self.GrossWeight) if self.GrossWeight else 0,
            "StoneWeight": float(self.StoneWeight) if self.StoneWeight else 0,
            "DiamondCarat": float(self.DiamondCarat) if self.DiamondCarat else 0,
            "ColourStoneCarat": float(self.ColourStoneCarat) if self.ColourStoneCarat else 0,
            "NetWeight": float(self.NetWeight) if self.NetWeight else 0,
            "MetalValue": float(self.MetalValue) if self.MetalValue else 0,
            "NetStoneValue": float(self.NetStoneValue) if self.NetStoneValue else 0,
            "NetDiamondValue": float(self.NetDiamondValue) if self.NetDiamondValue else 0,
            "NetColourStoneValue": float(self.NetColourStoneValue) if self.NetColourStoneValue else 0,
            "NetMCValue": float(self.NetMCValue) if self.NetMCValue else 0,
            "InvoiceAmt": float(self.InvoiceAmt) if self.InvoiceAmt else 0,
            "MCprofit": float(self.MCprofit) if self.MCprofit else 0,
            "StoneVAlueProfit": float(self.StoneVAlueProfit) if self.StoneVAlueProfit else 0,
            "Turnover": float(self.Turnover) if self.Turnover else 0,
            "TSK": self.TSK,
            "HourlyBillCount": self.HourlyBillCount,
            "PerMinuteBillCount": float(self.PerMinuteBillCount) if self.PerMinuteBillCount else 0,
            "BillTime": self.BillTime,
            "Country_Actual": self.Country_Actual
        }
