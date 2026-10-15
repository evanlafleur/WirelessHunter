company_ids.json   Bluetooth SIG company identifiers (code -> company name)
service_names.json standard GATT service UUIDs (16-bit, lowercase hex -> name)
Source: https://github.com/NordicSemiconductor/bluetooth-numbers-database (MIT licence).
Refresh by re-downloading v1/company_ids.json and v1/service_uuids.json and converting
to the compact {"code": "name"} / {"uuid": "name"} form.
