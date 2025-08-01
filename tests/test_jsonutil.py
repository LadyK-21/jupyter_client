"""Test suite for our JSON utilities."""
# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
import datetime
import json
import numbers
from datetime import timedelta
from unittest import mock

import pytest
from dateutil.tz import tzlocal, tzoffset

from jupyter_client import jsonutil
from jupyter_client.session import utcnow

REFERENCE_DATETIME = datetime.datetime(2013, 7, 3, 16, 34, 52, 249482, tzlocal())


class MyInt:
    def __int__(self):
        return 389


numbers.Integral.register(MyInt)


class MyFloat:
    def __float__(self):
        return 3.14


numbers.Real.register(MyFloat)


def test_parse_date_invalid():
    assert jsonutil.parse_date(None) is None
    assert jsonutil.parse_date("") == ""
    assert jsonutil.parse_date("invalid-date") == "invalid-date"


def test_parse_date_valid():
    ref = REFERENCE_DATETIME
    timestamp = "2013-07-03T16:34:52.249482Z"
    parsed = jsonutil.parse_date(timestamp)
    assert isinstance(parsed, datetime.datetime)


def test_parse_date_from_naive():
    ref = REFERENCE_DATETIME
    timestamp = "2013-07-03T16:34:52.249482"

    with pytest.deprecated_call(match="Interpreting naive datetime as local"):
        parsed = jsonutil.parse_date(timestamp)

    assert isinstance(parsed, datetime.datetime)
    assert parsed.tzinfo is not None
    assert parsed.tzinfo.utcoffset(ref) == tzlocal().utcoffset(ref)
    assert parsed == ref


def test_extract_date_from_naive():
    ref = REFERENCE_DATETIME
    timestamp = "2013-07-03T16:34:52.249482"

    with pytest.deprecated_call(match="Interpreting naive datetime as local"):
        extracted = jsonutil.extract_dates(timestamp)

    assert isinstance(extracted, datetime.datetime)
    assert extracted.tzinfo is not None
    assert extracted.tzinfo.utcoffset(ref) == tzlocal().utcoffset(ref)
    assert extracted == ref


def test_extract_dates_from_str():
    ref = REFERENCE_DATETIME
    timestamp = "2013-07-03T16:34:52.249482Z"
    extracted = jsonutil.extract_dates(timestamp)

    assert isinstance(extracted, datetime.datetime)
    assert extracted.tzinfo is not None
    assert extracted.tzinfo.utcoffset(ref) == timedelta(0)


def test_extract_dates_from_list():
    ref = REFERENCE_DATETIME
    timestamps = [
        "2013-07-03T16:34:52.249482Z",
        "2013-07-03T16:34:52.249482-0800",
        "2013-07-03T16:34:52.249482+0800",
        "2013-07-03T16:34:52.249482-08:00",
        "2013-07-03T16:34:52.249482+08:00",
    ]
    extracted = jsonutil.extract_dates(timestamps)
    for dt in extracted:
        assert isinstance(dt, datetime.datetime)
        assert dt.tzinfo is not None

    assert extracted[0].tzinfo.utcoffset(ref) == timedelta(0)
    assert extracted[1].tzinfo.utcoffset(ref) == timedelta(hours=-8)
    assert extracted[2].tzinfo.utcoffset(ref) == timedelta(hours=8)
    assert extracted[3].tzinfo.utcoffset(ref) == timedelta(hours=-8)
    assert extracted[4].tzinfo.utcoffset(ref) == timedelta(hours=8)


def test_extract_dates_from_dict():
    ref = REFERENCE_DATETIME
    timestamps = {
        0: "2013-07-03T16:34:52.249482Z",
        1: "2013-07-03T16:34:52.249482-0800",
        2: "2013-07-03T16:34:52.249482+0800",
        3: "2013-07-03T16:34:52.249482-08:00",
        4: "2013-07-03T16:34:52.249482+08:00",
    }
    extracted = jsonutil.extract_dates(timestamps)
    for k in extracted:
        dt = extracted[k]
        assert isinstance(dt, datetime.datetime)
        assert dt.tzinfo is not None

    assert extracted[0].tzinfo.utcoffset(ref) == timedelta(0)
    assert extracted[1].tzinfo.utcoffset(ref) == timedelta(hours=-8)
    assert extracted[2].tzinfo.utcoffset(ref) == timedelta(hours=8)
    assert extracted[3].tzinfo.utcoffset(ref) == timedelta(hours=-8)
    assert extracted[4].tzinfo.utcoffset(ref) == timedelta(hours=8)


def test_parse_ms_precision():
    base = "2013-07-03T16:34:52"
    digits = "1234567890"

    parsed = jsonutil.parse_date(base + "Z")
    assert isinstance(parsed, datetime.datetime)
    for i in range(len(digits)):
        ts = base + "." + digits[:i]
        parsed = jsonutil.parse_date(ts + "Z")
        if i >= 1 and i <= 6:
            assert isinstance(parsed, datetime.datetime)
        else:
            assert isinstance(parsed, str)


def test_json_default_datetime():
    naive = datetime.datetime.now()  # noqa
    local = tzoffset("Local", -8 * 3600)
    other = tzoffset("Other", 2 * 3600)
    data = dict(naive=naive, utc=utcnow(), withtz=naive.replace(tzinfo=other))
    with mock.patch.object(jsonutil, "tzlocal", lambda: local):  # noqa
        with pytest.deprecated_call(match="Please add timezone info"):
            jsondata = json.dumps(data, default=jsonutil.json_default)
    assert "Z" in jsondata
    assert jsondata.count("Z") == 1
    extracted = jsonutil.extract_dates(json.loads(jsondata))
    for dt in extracted.values():
        assert isinstance(dt, datetime.datetime)
        assert dt.tzinfo is not None


def test_json_default():
    # list of input/expected output.  Use None for the expected output if it
    # can be the same as the input.
    pairs: list = [
        (1, None),  # start with scalars
        (1.123, None),
        (1.0, None),
        ("a", None),
        (True, None),
        (False, None),
        (None, None),
        ({"key": b"\xFF"}, {"key": "/w=="}),
        # Containers
        ([1, 2], None),
        ((1, 2), [1, 2]),
        ({1, 2}, [1, 2]),
        (dict(x=1), None),
        ({"x": 1, "y": [1, 2, 3], "1": "int"}, None),
        # More exotic objects
        ((x for x in range(3)), [0, 1, 2]),
        (iter([1, 2]), [1, 2]),
        (MyFloat(), 3.14),
        (MyInt(), 389),
        (datetime.date(2025, 4, 8), "2025-04-08"),
    ]

    for val, jval in pairs:
        if jval is None:
            jval = val  # noqa
        out = json.loads(json.dumps(val, default=jsonutil.json_default))
        # validate our cleanup
        assert out == jval
