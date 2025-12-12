from rekkaribotti import get_licenseplate, generate_message, normalize__licenseplate, init_db
import re
import pytest
from requests.exceptions import RequestException

pattern = re.compile(r'\b[a-zA-ZäöÄÖ]{1,3}-?\d{1,3}\b')


def test_normalize_licenseplate():
    assert normalize__licenseplate("zgt800") == "ZGT-800"
    assert normalize__licenseplate("ZGT-800") == "ZGT-800"
    assert normalize__licenseplate("zGt800") == "ZGT-800"
    assert normalize__licenseplate("a123") == "A-123"
    assert normalize__licenseplate("mb1") == "MB-1"

def test_db():
    db = init_db(":memory:")
    cur = db.cursor()
    cur.execute("INSERT INTO manufacturer (name) VALUES (?)", ("TOYOTA",))
    cur.execute("INSERT INTO model (modelName, description) VALUES (?, ?)", ("COROLLA", "Toyota Corolla"))
    cur.execute("INSERT INTO vehicle (licensePlate, manufacturer, modelName, registerDate) VALUES (?, ?, ?, ?)",
                ("ZGT-800", "TOYOTA", "COROLLA", "1998-01-05"))
    db.commit()

    cur.execute("SELECT * FROM manufacturer WHERE name = ?", ("TOYOTA",))
    row = cur.fetchone()
    assert row["name"] == "TOYOTA"

    cur.execute("SELECT * FROM model WHERE modelName = ?", ("COROLLA",))
    row = cur.fetchone()
    assert row["description"] == "Toyota Corolla"

    cur.execute("SELECT * FROM vehicle WHERE licensePlate = ?", ("ZGT-800",))
    row = cur.fetchone()
    assert row["manufacturer"] == "TOYOTA"
    assert row["modelName"] == "COROLLA"
    assert row["registerDate"] == "1998-01-05"

def test_get_licenseplate():
    db = db = init_db(":memory:")
    cur_new = db.cursor()
    licenseplate = pattern.search("zgt800")
    licenseplate = pattern.search(normalize__licenseplate(licenseplate.group()))
    data = get_licenseplate(licenseplate)
    assert data["manufacturer"] == "Toyota"
    assert data["modelName"] == "Corolla 4-ovi Sedan"
    assert data["registerDate"] == "1998-01-05"
    assert data["vinNumber"] == "JT153EEB100018333"

def test_exceptions():
    licenseplate = pattern.search("zgt801")
    licenseplate = pattern.search(normalize__licenseplate(licenseplate.group()))
    with pytest.raises(RequestException) as excinfo:
        data = get_licenseplate(licenseplate)
        assert "HTTP: 400" in str(excinfo.value)