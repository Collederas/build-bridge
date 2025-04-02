from publisher.steam.steam_publisher import SteamPublisher
# TODO: Add imports for EpicPublisher, etc.

class PublisherFactory:
    @staticmethod
    def get_publisher(store_name, build_path):
        """Return the appropriate publisher instance based on store name."""
        publishers = {
            "steam": SteamPublisher,
            # "epic": EpicPublisher,  # Add later
        }
        publisher_class = publishers.get(store_name.lower())
        if not publisher_class:
            raise ValueError(f"Unsupported store: {store_name}")
        return publisher_class(build_path)