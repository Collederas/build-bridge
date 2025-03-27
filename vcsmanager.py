class VCSManager:
    config = {}

    def __init__(self):
        config = self.load_config()
        if not config:
            self.update_log("VCS configuration not found. Please set it up.")
            return
        
    def load_config():
        raise NotImplementedError

    def sync_repo():
        raise NotImplementedError
    