"""The restocking engine. Read only: nothing in this package writes a document.

settings.py  the shop's choices, with the defaults that make day one work
access.py    who may see what (roles, the on/off switches, warehouse permissions)
data.py      bulk reads from ERPNext's own tables (Bin, Stock Ledger, invoices)
model.py     the arithmetic, pure functions with no database
engine.py    puts them together for one company
"""
