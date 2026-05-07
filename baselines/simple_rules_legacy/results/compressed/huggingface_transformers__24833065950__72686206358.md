# CI Log (compressed)

**Sections:** 45 total, 1 with failures

## Failures

### ❌ _between_groups `[generic]` (orig 87 lines, id=s_ccb7a3d3)
```
doc_folder has been set to transformers/docs/source
Generating docs for language en
Building docs for transformers ../transformers/docs/source/en ../build_dir/transformers/pr_45433/en
Building the MDX files:   0%|          | 0/690 [00:00<?, ?it/s]
Building the MDX files:   6%|▌         | 38/690 [00:02<00:39, 16.34it/s]
Building the MDX files:  15%|█▌        | 104/690 [00:08<00:45, 12.99it/s]
Traceback (most recent call last):
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/doc_builder/build_doc.py", line 222, in build_mdx_files
    content, new_anchors, source_files, errors = resolve_autodoc(
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/doc_builder/build_doc.py", line 148, in resolve_autodoc
    doc = autodoc_svelte(
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/doc_builder/autodoc.py", line 607, in autodoc_svelte
    obj = find_object_in_package(object_name=object_name, package=package)
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/doc_builder/autodoc.py", line 40, in find_object_in_package
    submodule = getattr(module, split, None)
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/transformers/utils/import_utils.py", line 2212, in __getattr__
    module = self._get_module(self._class_to_module[name])
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/transformers/utils/import_utils.py", line 2446, in _get_module
    raise e
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/transformers/utils/import_utils.py", line 2444, in _get_module
    return importlib.import_module("." + module_name, self.__name__)
  File "/usr/lib/python3.10/importlib/__init__.py", line 126, in import_module
[... 5 lines elided ...]
  File "<frozen importlib._bootstrap_external>", line 883, in exec_module
  File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/transformers/models/llama/modeling_llama.py", line 30, in <module>
    from ...modeling_layers import (
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/transformers/modeling_layers.py", line 27, in <module>
    from .processing_utils import Unpack
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/transformers/processing_utils.py", line 79, in <module>
    from .modeling_utils import PreTrainedAudioTokenizerBase
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/transformers/modeling_utils.py", line 1974
    <<<<<<< sonic-moe
    ^^
SyntaxError: invalid syntax
The above exception was the direct cause of the following exception:
Traceback (most recent call last):
  File "/home/runner/work/transformers/transformers/.venv/bin/doc-builder", line 10, in <module>
    sys.exit(main())
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/doc_builder/commands/doc_builder_cli.py", line 50, in main
    args.func(args)
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/doc_builder/commands/build.py", line 103, in build_command
    build_doc(
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/doc_builder/build_doc.py", line 397, in build_doc
    anchors_mapping, source_files_mapping = build_mdx_files(
  File "/home/runner/work/transformers/transformers/.venv/lib/python3.10/site-packages/doc_builder/build_doc.py", line 255, in build_mdx_files
    raise type(e)(f"There was an error when converting {file} to the MDX format.\n" + e.args[0]) from e
SyntaxError: There was an error when converting ../transformers/docs/source/en/model_doc/llama.md to the MDX format.
invalid syntax
##[error]Process completed with exit code 1.
Post job cleanup.
[command]/usr/bin/git version
git version 2.53.0
Temporarily overriding HOME='/home/runner/work/_temp/827b5e4f-287b-43a7-a2ca-4967b1ffd64b' before making global git config changes
Adding repository directory to the temporary git global config as a safe directory
[command]/usr/bin/git config --global --add safe.directory /home/runner/work/transformers/transformers/transformers
[command]/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
[command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
[command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
http.https://github.com/.extraheader
[command]/usr/bin/git config --local --unset-all http.https://github.com/.extraheader
[command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
[command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
[command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
Post job cleanup.
```

## Passing sections (summarized)

- **_preamble** `[generic]` (1 lines → 1 kept, id=s_b8f696d3)
- **Runner Image Provisioner** `[generic]` (6 lines → 6 kept, id=s_e7f4a387)
- **Operating System** `[generic]` (3 lines → 3 kept, id=s_1c324472)
- **Runner Image** `[generic]` (4 lines → 4 kept, id=s_970d65fd)
- **GITHUB_TOKEN Permissions** `[generic]` (3 lines → 3 kept, id=s_2d8f09c2)
- **_between_groups** `[generic]` (9 lines → 9 kept, id=s_8a8beb02)
- **Inputs** `[generic]` (17 lines → 17 kept, id=s_f9dbfece)
- **_between_groups** `[generic]` (1 lines → 1 kept, id=s_85b12b1b)
- **Run actions/checkout@v4** `[generic]` (19 lines → 19 kept, id=s_ef13cb30)
- **_between_groups** `[generic]` (1 lines → 1 kept, id=s_51c5a421)
- **Getting Git version info** `[generic]` (3 lines → 3 kept, id=s_f995f891)
- **_between_groups** `[generic]` (3 lines → 3 kept, id=s_96c71bfc)
- **Initializing the repository** `[generic]` (16 lines → 16 kept, id=s_811d03c3)
- **Disabling automatic garbage collection** `[generic]` (1 lines → 1 kept, id=s_e0d1438b)
- **Setting up auth** `[generic]` (7 lines → 7 kept, id=s_3abf45bb)
- **Fetching the repository** `[generic]` (3 lines → 3 kept, id=s_39015be1)
- **Determining the checkout info** `[generic]` (2 lines → 2 kept, id=s_70584223)
- **_between_groups** `[generic]` (2 lines → 2 kept, id=s_44f206cd)
- **Checking out the ref** `[generic]` (3 lines → 3 kept, id=s_dad9d629)
- **_between_groups** `[generic]` (2 lines → 2 kept, id=s_33ee6321)
- **Run actions/checkout@v4** `[generic]` (18 lines → 18 kept, id=s_8171f0b7)
- **_between_groups** `[generic]` (1 lines → 1 kept, id=s_3862f0fb)
- **Getting Git version info** `[generic]` (3 lines → 3 kept, id=s_df3aacb4)
- **_between_groups** `[generic]` (3 lines → 3 kept, id=s_33a8701d)
- **Initializing the repository** `[generic]` (16 lines → 16 kept, id=s_e3a953be)
- **Disabling automatic garbage collection** `[generic]` (1 lines → 1 kept, id=s_2fdf06fd)
- **Setting up auth** `[generic]` (7 lines → 7 kept, id=s_b9704db8)
- **Fetching the repository** `[generic]` (3 lines → 3 kept, id=s_10e1b578)
- **_between_groups** `[generic]` (2 lines → 2 kept, id=s_5771f07a)
- **Checking out the ref** `[generic]` (19 lines → 12 kept, id=s_d2370319)
- **_between_groups** `[generic]` (2 lines → 2 kept, id=s_0344580a)
- **Run actions/setup-node@v4** `[generic]` (9 lines → 9 kept, id=s_ccc5b826)
- **_between_groups** `[generic]` (1 lines → 1 kept, id=s_fe9901af)
- **Environment details** `[generic]` (3 lines → 3 kept, id=s_c960aa1e)
- **Run if [ -z "" ]** `[generic]` (10 lines → 10 kept, id=s_6803c2d5)
- **Run if [ -z "" ]** `[generic]` (11 lines → 11 kept, id=s_0b4e88ed)
- **Run if [ -z "" ]** `[generic]` (27 lines → 25 kept, id=s_23b538dc)
- **_between_groups** `[generic]` (1 lines → 1 kept, id=s_3e26f090)
- **Run pip install -U uv** `[generic]` (10 lines → 10 kept, id=s_020861b4)
- **_between_groups** `[generic]` (9 lines → 9 kept, id=s_9a87ed2d)
- **Run source .venv/bin/activate** `[generic]` (25 lines → 24 kept, id=s_5150854b)
- **_between_groups** `[pytest]` (356 lines, elided)
- **Run source .venv/bin/activate** `[generic]` (14 lines → 14 kept, id=s_db30c8eb)
- **Run source .venv/bin/activate** `[generic]` (42 lines → 39 kept, id=s_8cb58c2d)