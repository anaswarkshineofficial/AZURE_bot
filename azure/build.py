from __future__ import annotations

from azure.builders.pvp_builder import PvpBuilder
from azure.builders.rp_builder import RpBuilder
from azure.builders.gaming_builder import GamingBuilder
from azure.builders.esports_builder import EsportsBuilder
from azure.builders.community_builder import CommunityBuilder


def get_builder(guild, admin_user, template_name: str):
    mapping = {
        "pvp": PvpBuilder,
        "rp": RpBuilder,
        "gaming": GamingBuilder,
        "esports": EsportsBuilder,
        "community": CommunityBuilder,
    }
    builder_class = mapping.get(template_name.lower(), PvpBuilder)
    return builder_class(guild, admin_user, template_name)
