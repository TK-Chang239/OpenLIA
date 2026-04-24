from openlia.departments import get_department
from openlia.departments.panic_thermometer import PanicThermometerDepartment


def test_panic_thermometer_registered():
    d = get_department("panic_thermometer")
    assert isinstance(d, PanicThermometerDepartment)
