#### *0.6.5* @ 2020-07-10
* changed `AppTestCase.get_app_by_type` to `AppTestCase.get_apps_by_type`
* added `AppTestCase.add_apps_by_type`
* added `@app` iterator
* added `App.stop_nodes`
* pull `JavaApp.wait_message` up to `App`
* added `verbose` kwarg to `Ignite.start_nodes`, default `False` aka `-DIGNITE_QUIET=true` 
* added `num_nodes` app option to `Ignite`
* added `num_nodes` app option to `JavaApp`
* added `get_node_env`, `get_node_run_dir` to `JavaApp`
* fixed `JavaApp.check_requirements` use artifact name instead of app name

#### *0.6.4* @ 2020-06-24
* added `use_ssh_agent` option to environment config to allow SshPool use SSH Agent

#### *0.6.3* @ 2020-06-08
* added base `JavaApp` application
* added latest `ControlUtility` commands for AI 2.9.0
* added `download_from_nodes` to `SshPool`
* added `local_run` to `tiden.util`
* changed `download_from_host` now supports lists of remote files or map of host -> files
* changed `download` now returns list of downloaded local file paths 
* fixed console entrypoint
* fixed `LocalPool` usage in tests
* fixed config load plugin call
* fixed module/class cache to `TidenRunner` to prevent double importing due to `check_requirements`

#### *0.6.2* @ 2020-06-05
* added license banners to all sources files
* added `after_config_loaded` hook
* moved bin scripts under generic `tiden` entry point
* added `EnvExpander` plugin
* added `FtpDownloader` plugin
* merged combinator and yardstick related fixes from baseline repo

#### *0.6.1* @ 2020-05-27
* added `before_prepare_artifacts` hook
* fixed `test_prepare_artifacts` failed on MacOs
* remove GridGain Ultimate parts from `ControlUtility` and `Ignite`
* updated README.md
     
#### *0.6.0* @ 2020-05-20
* Initial fork to PyPI
