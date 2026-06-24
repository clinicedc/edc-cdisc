from __future__ import annotations

import warnings
from collections.abc import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from edc_sites.site import sites as site_sites
from lxml import etree

from ..constants import (
    LOCATION,
    SITE_LOCATION_TYPE,
    USER,
    USER_TYPE_OTHER,
)
from ..utils import oid

# settings map: edc_auth Role.name -> ODM User@UserType; anything not listed
# (and any user with no listed role) defaults to USER_TYPE_OTHER.  Field clinical
# staff are "Other", not "Investigator".
USER_TYPE_BY_ROLE_SETTING = "EDC_CDISC_USER_TYPE_BY_ROLE"
# applied in priority order when a user holds several mapped roles
USER_TYPE_PRIORITY = ("Sponsor", "Investigator", "Lab")


class AdminDataMixin:
    """Builds ODM ``AdminData`` (``User`` + ``Location``) for the users and
    sites referenced by the exported audit records.

    ODM 1.3.1 ``User``/``Location`` are closed types (no ``Alias``/extension),
    so edc_auth roles can only be expressed coarsely via ``User@UserType``.
    """

    @staticmethod
    def user_type_for_roles(role_names: Iterable[str]) -> str:
        mapping = getattr(settings, USER_TYPE_BY_ROLE_SETTING, {}) or {}
        mapped = {mapping[name] for name in role_names if name in mapping}
        for user_type in USER_TYPE_PRIORITY:
            if user_type in mapped:
                return user_type
        return USER_TYPE_OTHER

    def build_admin_data(
        self,
        usernames: Iterable[str],
        site_ids: Iterable[int],
        metadata_version_oid: str,
    ) -> etree._Element:
        element = etree.Element("AdminData", StudyOID=self.protocol_oid)
        for username in sorted(usernames):
            element.append(self.build_user_element(username))
        for site_id in sorted(site_ids):
            element.append(self.build_location_element(site_id, metadata_version_oid))
        return element

    def build_user_element(self, username: str) -> etree._Element:
        user_model_cls = get_user_model()
        user = user_model_cls.objects.filter(username=username).first()
        if user is None:
            # still emit a minimal User so the AuditRecord UserRef resolves
            element = etree.Element("User", OID=oid(USER, username))
            etree.SubElement(element, "LoginName").text = username
            return element

        profile = getattr(user, "userprofile", None)
        role_names = {role.name for role in profile.roles.all()} if profile else set()
        institution = (getattr(profile, "institution", "") if profile else "") or (
            self.protocol_config.institution
        )
        user_site_ids = sorted(site.id for site in profile.sites.all()) if profile else []

        element = etree.Element(
            "User",
            OID=oid(USER, username),
            UserType=self.user_type_for_roles(role_names),
        )
        # children in XSD order: LoginName, FirstName, LastName, Organization,
        # Email, LocationRef
        etree.SubElement(element, "LoginName").text = username
        if user.first_name:
            etree.SubElement(element, "FirstName").text = user.first_name
        if user.last_name:
            etree.SubElement(element, "LastName").text = user.last_name
        if institution:
            etree.SubElement(element, "Organization").text = institution
        if user.email:
            etree.SubElement(element, "Email").text = user.email
        for site_id in user_site_ids:
            etree.SubElement(element, "LocationRef", LocationOID=oid(LOCATION, str(site_id)))
        return element

    def build_location_element(
        self, site_id: int, metadata_version_oid: str
    ) -> etree._Element:
        try:
            name = site_sites.get(site_id).title
        except Exception:  # unknown/unregistered site → fall back to the id
            warnings.warn(
                f"Site id {site_id} not in edc_sites registry; using id as Name.",
                UserWarning,
                stacklevel=2,
            )
            name = str(site_id)
        element = etree.Element(
            "Location",
            OID=oid(LOCATION, str(site_id)),
            Name=str(name),
            LocationType=SITE_LOCATION_TYPE,
        )
        etree.SubElement(
            element,
            "MetaDataVersionRef",
            StudyOID=self.protocol_oid,
            MetaDataVersionOID=metadata_version_oid,
            EffectiveDate=self.protocol_config.study_open_datetime.date().isoformat(),
        )
        return element
