"""Synthetic policy clauses + benchmark queries (authored for this project; no real policy)."""
# (doc, section, claim_type, restricted, text, [benchmark queries])
RAW = [
("POL-AUTO","3.1","auto_collision",False,"Collision damage to the insured vehicle is covered when the driver holds a valid licence and an accident report is provided.",["is my crash covered if I have a licence","what report do I need for a car accident"]),
("POL-AUTO","3.2","auto_collision",False,"Third party liability covers injury and property damage caused to other drivers up to the legal limit; the other party's details are required.",["who pays for damage I cause to another driver","do I need the other driver's details"]),
("POL-AUTO","3.3","auto_collision",False,"Repair estimates must come from an approved workshop and the payout cannot exceed the market value of the vehicle.",["which workshop can issue the repair quote","maximum payout compared to car value"]),
("POL-AUTO","3.4","auto_collision",False,"Glass and windscreen breakage is covered with a fixed excess of 50 EUR and no loss of bonus.",["broken windscreen excess amount","does glass damage affect my no-claims bonus"]),
("POL-AUTO","3.5","auto_collision",False,"Driving under the influence of alcohol or drugs voids collision coverage.",["drunk driving accident coverage","is a crash covered if the driver took drugs"]),
("POL-HOME","5.1","property_damage",False,"Water, storm and fire damage to the insured home is covered; photos and a repair estimate are required.",["flood in kitchen from burst pipe","storm damaged roof tiles"]),
("POL-HOME","5.2","property_damage",False,"Gradual leaks, damp and lack of maintenance are excluded from cover.",["slow leak damp walls covered","damage from poor maintenance"]),
("POL-HOME","5.3","property_damage",False,"Contents insurance covers furniture and appliances up to the declared sum insured with an inventory list.",["are my appliances covered after a fire","inventory list for damaged furniture"]),
("POL-HOME","5.4","property_damage",False,"Emergency repairs to prevent further damage are reimbursed up to 500 EUR when invoices are supplied.",["emergency plumber reimbursement","temporary repairs to stop more damage"]),
("POL-HOME","5.5","property_damage",False,"Natural disasters declared by the authorities are handled by the national compensation consortium.",["earthquake declared disaster who pays","natural catastrophe claim consortium"]),
("POL-THEFT","2.1","theft",False,"Theft and burglary require a police report filed within 72 hours and proof of ownership.",["how long to file a police report after burglary","proof that I owned the stolen item"]),
("POL-THEFT","2.2","theft",False,"Items stolen from unattended vehicles are covered only if they were stored in the locked boot.",["laptop stolen from car seat","stolen stereo from locked car"]),
("POL-THEFT","2.3","theft",False,"Mobile phones and electronics are covered against theft with violence or forced entry, not simple loss.",["phone lost versus stolen coverage","snatched phone from bag"]),
("POL-THEFT","2.4","theft",False,"Bicycles are covered when secured with an approved lock; the lock receipt must be provided.",["stolen bicycle lock receipt","is my bike covered if not locked"]),
("POL-THEFT","2.5","theft",False,"Cash and jewellery theft is limited to 1000 EUR unless declared on the policy schedule.",["stolen jewellery limit","cash stolen from home maximum"]),
("POL-HEALTH","7.1","health",False,"Medical expenses after an accident are reimbursed against original invoices and a medical report, subject to the annual limit.",["reimbursement hospital bills accident","what documents for medical expense claim"]),
("POL-HEALTH","7.2","health",False,"Physiotherapy is covered up to 20 sessions per year with a prescription from a physician.",["how many physio sessions covered","prescription needed for physiotherapy"]),
("POL-HEALTH","7.3","health",False,"Pre-existing conditions are excluded during the first 12 months of the policy.",["pre-existing illness waiting period","condition that existed before policy start"]),
("POL-HEALTH","7.4","health",False,"Hospital surgery requires prior authorization except in emergencies.",["authorization before planned surgery","emergency operation without approval"]),
("POL-HEALTH","7.5","health",False,"Dental and optical treatments are covered only when caused by an accident.",["dentist broken tooth after fall","glasses broken in accident"]),
("INTERNAL-GUIDE","1.1","general",True,"INTERNAL: claims above 5000 EUR must be escalated to a senior specialist and checked for fraud indicators.",["high value claim escalation senior specialist"]),
]
CLAUSES = [{"id": f"{d}#{s}", "doc_id": d, "section": s, "type": t, "restricted": r, "text": x, "queries": q} for d, s, t, r, x, q in RAW]
