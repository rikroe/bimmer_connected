"""Models the state of a vehicle."""

import datetime
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from bimmer_connected.const import ATTR_ATTRIBUTES, ATTR_STATE
from bimmer_connected.models import StrEnum, ValueWithUnit, VehicleDataBase
from bimmer_connected.utils import parse_datetime

_LOGGER = logging.getLogger(__name__)


class ConditionBasedServiceStatus(StrEnum):
    """Status of the condition based services."""

    OK = "OK"
    OVERDUE = "OVERDUE"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


@dataclass
class ConditionBasedService:
    """Entry in the list of condition based services."""

    service_type: str
    state: ConditionBasedServiceStatus
    due_date: Optional[datetime.datetime]
    due_distance: ValueWithUnit

    @classmethod
    def from_api_entry(
        cls,
        type: str,  # noqa: A002, pylint: disable=redefined-builtin
        status: str,
        dateTime: Optional[str] = None,  # noqa: N803
        mileage: Optional[int] = None,
        **kwargs,
    ):
        """Parse a condition based service entry from the API format to `ConditionBasedService`."""
        due_distance = ValueWithUnit(mileage, "km") if mileage else ValueWithUnit(None, None)
        due_date = parse_datetime(dateTime) if dateTime else None
        return cls(type, ConditionBasedServiceStatus(status), due_date, due_distance)


@dataclass
class ConditionBasedServiceReport(VehicleDataBase):
    """Parse and summarizes condition based services (e.g. next oil service)."""

    messages: List[ConditionBasedService] = field(default_factory=list)
    """List of the condition based services."""

    is_service_required: bool = False
    """Indicate if a service is required."""

    next_service_by_distance: Optional[ConditionBasedService] = None
    """Next service by distance."""

    next_service_by_time: Optional[ConditionBasedService] = None
    """Next service by due date."""

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: Dict) -> Optional[Dict]:
        """Parse doors and windows."""
        retval: Dict[str, Any] = {}

        if ATTR_STATE in vehicle_data and (messages := vehicle_data[ATTR_STATE].get("requiredServices")):
            retval["messages"] = [ConditionBasedService.from_api_entry(**m) for m in messages]
            retval["is_service_required"] = any((m.state != ConditionBasedServiceStatus.OK) for m in retval["messages"])

            retval["next_service_by_distance"] = next(
                iter(
                    sorted(
                        [m for m in retval["messages"] if m.due_distance.value is not None],
                        key=lambda x: f"{x.due_distance.value:010}-{x.service_type}",
                    )
                ),
                None,
            )

            retval["next_service_by_time"] = next(
                iter(
                    sorted(
                        [m for m in retval["messages"] if m.due_date is not None],
                        key=lambda x: f"{x.due_date!s}-{x.service_type}",
                    )
                ),
                None,
            )

        return retval


class CheckControlStatus(StrEnum):
    """Status of the condition based services."""

    OK = "OK"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


@dataclass
class CheckControlMessage:
    """Check control message sent from the server."""

    description_short: str
    description_long: Optional[str]
    state: CheckControlStatus

    @classmethod
    def from_api_entry(
        cls,
        type: str,  # noqa: A002, pylint: disable=redefined-builtin
        severity: str,
        longDescription: Optional[str] = None,  # noqa: N803
        **kwargs,
    ):
        """Parse a check control entry from the API format to `CheckControlMessage`."""
        return cls(type, longDescription, CheckControlStatus(severity))


@dataclass
class CheckControlMessageReport(VehicleDataBase):
    """Parse and summarizes check control messages (e.g. low tire pressure)."""

    messages: List[CheckControlMessage] = field(default_factory=list)
    """List of check control messages."""

    has_check_control_messages: bool = False
    """Indicate if check control messages are present."""

    urgent_check_control_messages: Optional[str] = None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: Dict) -> Optional[Dict]:
        """Parse doors and windows."""
        retval: Dict[str, Any] = {}

        if ATTR_STATE in vehicle_data and (messages := vehicle_data[ATTR_STATE].get("checkControlMessages")):
            retval["messages"] = [CheckControlMessage.from_api_entry(**m) for m in messages if m["severity"] != "OK"]
            retval["has_check_control_messages"] = len([m for m in retval["messages"] if m.state != "LOW"]) > 0
            retval["urgent_check_control_messages"] = (
                ", ".join([m.description_short for m in retval["messages"] if m.state != "LOW"])
                if retval["has_check_control_messages"]
                else None
            )

        return retval


@dataclass
class Headunit(VehicleDataBase):
    """Parse and summarizes headunit hard/software versions."""

    idrive_version: str = ""
    """IDRIVE generation."""

    headunit_type: str = ""
    """Type of headunit."""

    software_version: str = ""
    """Current software revision of vehicle"""

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: Dict) -> Optional[Dict]:
        """Parse headunit hard/software."""
        retval: Dict[str, Any] = {}

        if ATTR_ATTRIBUTES in vehicle_data and (
            software_version := vehicle_data[ATTR_ATTRIBUTES].get("softwareVersionCurrent")
        ):
            retval["idrive_version"] = vehicle_data[ATTR_ATTRIBUTES]["hmiVersion"]
            retval["headunit_type"] = vehicle_data[ATTR_ATTRIBUTES]["headUnitType"]

            istep = software_version["iStep"]
            month = software_version["puStep"]["month"]
            year = software_version["puStep"]["year"]
            model_year = vehicle_data[ATTR_ATTRIBUTES]["year"]

            retval["software_version"] = f"{month:02d}/{str(model_year)[:2]}{year:02d}.{str(istep)[1:]}"

        return retval
