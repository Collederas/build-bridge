import pytest

from build_bridge.core.builder.unreal_builder import UnrealBuilder
from build_bridge.views.widgets.build_targets_widget import BuildTargetRow


def _make_unreal_builder(tmp_path, maps):
    project_dir = tmp_path / "Project"
    project_dir.mkdir()
    (project_dir / "MyGame.uproject").write_text('{"EngineAssociation": "5.3"}')

    engine_dir = tmp_path / "UE_5.3"
    batch_files_dir = engine_dir / "Engine" / "Build" / "BatchFiles"
    batch_files_dir.mkdir(parents=True)
    (batch_files_dir / "RunUAT.bat").touch()
    (batch_files_dir / "RunUAT.sh").touch()

    target_file = project_dir / "Source" / "MyGame.Target.cs"
    target_file.parent.mkdir()
    target_file.touch()

    return UnrealBuilder(
        source_dir=str(project_dir),
        engine_path=str(engine_dir),
        target_platform="Win64",
        target_config="Shipping",
        target=str(target_file),
        maps=maps,
        output_dir=str(tmp_path / "Builds" / "MyGame"),
    )


class TestUnrealBuilderMaps:
    def test_build_command_passes_target_maps_as_single_uat_argument(self, tmp_path):
        builder = _make_unreal_builder(
            tmp_path,
            ["/Game/Maps/MainMenu", "/Game/Maps/Arena"],
        )

        command = builder.get_build_command()

        assert command.count("-map=/Game/Maps/MainMenu+/Game/Maps/Arena") == 1
        assert not any(arg == "-map=/Game/Maps/MainMenu" for arg in command)
        assert not any(arg == "-map=/Game/Maps/Arena" for arg in command)

    def test_build_command_omits_empty_map_argument(self, tmp_path):
        builder = _make_unreal_builder(tmp_path, [])

        command = builder.get_build_command()

        assert not any(arg.startswith("-map=") for arg in command)


class TestUmapPathConversion:
    def test_project_content_root_map_has_no_double_slash(self, tmp_path):
        project_dir = tmp_path / "Project"
        map_path = project_dir / "Content" / "Startup.umap"
        map_path.parent.mkdir(parents=True)
        map_path.touch()

        converted = BuildTargetRow._convert_umap_path(None, str(map_path), str(project_dir))

        assert converted == "/Game/Startup"

    def test_project_nested_map_uses_game_mount(self, tmp_path):
        project_dir = tmp_path / "Project"
        map_path = project_dir / "Content" / "Maps" / "Arena.umap"
        map_path.parent.mkdir(parents=True)
        map_path.touch()

        converted = BuildTargetRow._convert_umap_path(None, str(map_path), str(project_dir))

        assert converted == "/Game/Maps/Arena"

    def test_plugin_map_uses_plugin_mount_name(self, tmp_path):
        project_dir = tmp_path / "Project"
        map_path = (
            project_dir
            / "Plugins"
            / "DungeonKit"
            / "Content"
            / "Maps"
            / "Dungeon.umap"
        )
        map_path.parent.mkdir(parents=True)
        map_path.touch()

        converted = BuildTargetRow._convert_umap_path(None, str(map_path), str(project_dir))

        assert converted == "/DungeonKit/Maps/Dungeon"

    def test_game_feature_plugin_map_uses_plugin_mount_name(self, tmp_path):
        project_dir = tmp_path / "Project"
        map_path = (
            project_dir
            / "Plugins"
            / "GameFeatures"
            / "ShooterCore"
            / "Content"
            / "Maps"
            / "WorldMap2.umap"
        )
        map_path.parent.mkdir(parents=True)
        map_path.touch()

        converted = BuildTargetRow._convert_umap_path(None, str(map_path), str(project_dir))

        assert converted == "/ShooterCore/Maps/WorldMap2"

    def test_rejects_paths_outside_project_directory(self, tmp_path):
        project_dir = tmp_path / "Project"
        other_dir = tmp_path / "ProjectSibling"
        map_path = other_dir / "Content" / "Other.umap"
        map_path.parent.mkdir(parents=True)
        map_path.touch()

        with pytest.raises(ValueError, match="not within"):
            BuildTargetRow._convert_umap_path(None, str(map_path), str(project_dir))
