import pytest

from build_bridge.core.builder.unreal_builder import BuildAlreadyExistsError, UnrealBuilder


def _make_unreal_builder(tmp_path, output_dir=None, allow_existing_output_dir=False):
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
        output_dir=str(output_dir or tmp_path / "Builds" / "MyGame"),
        allow_existing_output_dir=allow_existing_output_dir,
    )


class TestUnrealBuilderCommand:
    def test_build_command_has_no_map_argument(self, tmp_path):
        builder = _make_unreal_builder(tmp_path)

        command = builder.get_build_command()

        assert not any(arg.startswith("-map=") for arg in command)

    def test_existing_output_directory_is_rejected_by_default(self, tmp_path):
        output_dir = tmp_path / "Builds" / "MyGame"
        output_dir.mkdir(parents=True)

        with pytest.raises(BuildAlreadyExistsError):
            _make_unreal_builder(tmp_path, output_dir=output_dir)

    def test_existing_prepared_output_directory_can_be_allowed(self, tmp_path):
        output_dir = tmp_path / "Builds" / "MyGame"
        output_dir.mkdir(parents=True)

        builder = _make_unreal_builder(
            tmp_path,
            output_dir=output_dir,
            allow_existing_output_dir=True,
        )

        assert builder.output_dir == str(output_dir)
