# Tiden 0.6.2

## 1. What is Tiden?

The test framework for testing Apache Ignite in distributed environment
(**T**esting **I**gnite in **D**istributed **EN**vironment).

## 2. Requirements.

Python 3.7 with installed modules on the host starting tests:
* PyYaml
* psutil
* jinja2
* requests (optional)
* ansible (optional)
* py4j (optional)

Environment:
* The hosts running under *NIX bases OS (RedHat, CentOS, Ubuntu) 
with installed `bash` and regular commands like `cat, grep, ls, head, ps`. 
* Public/private SSH keys authentication without password prompt from 
the host starting tests.
* There is no running java processes by default. Tiden removes all 
java processes by `sudo killall -9 java`. Thus you must add killall to sudoers list with no password.

## 3. Command-line arguments.

```bash
tiden run-tests \
  --tc=<path_to_configuration_file> \
  --tc=<path_to_configuration_file> \
  --to=<option_path>=<option_value> \
  --to=<option_path>=<option_value> \
  --ts=<suite_name>.<test_module_name> \
  --var_dir=<path_to_work_directory> \
  --clean=all \
  --attr=<attr1> \
  --attr=<attr2> \
  --collect-only
```

* `--tc=<path_to_configuration_file>`

Argument type: **mandatory** 

Tiden uses one or more YAML formatted configuration file to construct
the test configuration that should like following:

```yaml
artifacts:
 <artifact_1_name>:
  glob_path: <local_path_to_artifact>
  type: [ignite|...]
 <artifact_2_name>:
  glob_path: <local_path_to_artifact>
  type: [ignite|...]
environment:
 username: <user_name>
 private_key_path: <local_path_to_private_key>
 server_hosts: [<ip_address_of_host_1>, <ip_address_of_host_2>,...]
 common_hosts: [<ip_address_of_host_1>, <ip_address_of_host_2>,...]
 client_hosts: [<ip_address_of_host_1>, <ip_address_of_host_2>,...]
 home: <remote_path_for_tiden>
```
_Note: use '.' (dot) in key names is forbidden._
_All passed configuration files merged into one_ 

* `--ts=<suite_name>.<test_module_name>`

Argument type: **mandatory** 

The suite is name of directory in `./suites`.

The test module name is the name of python module in the suite directory.

* `--var_dir=<path_to_existing_directory>`

Argument type: **optional** 

The directory to collect test artifacts, reports, temporary files.

By default the directory is `./var`

* `--to=<key_path>=<value>`

Argument type: **optional** 

Override the option of test configuration.

\<key_path\> is path to a key to override delimited by dots e.g. 
`--to=key1.key2.key3=<value>`:

```yaml
key1:
 key2:
  key3: value
```

If the original value is the list then new value can be provided as the string of values delimited by commas:

```bash
tiden run-tests ... --to=<key_path>=value1,value2,value3
```

If you provide the `+` symbol before the list of values, then these values will be appended to ones already 
set for the given configuration option:

```bash
tiden run-tests ... --to=<key_path>=+value1,value2,value3
```

##### Clean
* `--clean=[mode]`

Argument type: **optional**

Modes:
- `all` - clean up local `var_dir` and remote `environment.home` directory 
- `tests` - clean up local tests dirs , but didn't repack already collected artifacts. Also clean tests data from `environment.home` directory 
- `remote_tests` - same as `tests`, but didn't clean local tests data


##### Attr
* `--attr=<attr>`

Argument type: **optional**

Choose the test methods decorated by `@attr('<attr_name>')`.

The multiple usage of that argument processed by following rules:

By default or if `--to=attr_match=any`: any test method will be executed 
if at least one from provided attributes found in the attribute 
decoration list of that method.

If `--to=attr_match=all` then all provided attributes should be a subset
of attribute decoration list of that method.

##### Collect tests
* `--collect-only`

Argument type: **optional**

Settings this option makes Tiden only enumerate and print test names matching to given `--ts` and `--attr` values,
but do not run any tests. Note, that artifacts are still processed and repacked to allow conditional skips work.   


## 4. Tests

* The rules to create a test:

1. Create a python module prefixed by `test_` (and in lower case) 
in the chosen suite directory.
2. The created test python module must contain single class only.
3. The name of module must reflect the name of class: `test_new_feature.py` to
`TestNewFeature` class.
4. The resource directory should be called as test module name without 
`test_` prefix: `test_new_feature.py` to `res/new_feature`.
5. The test class must be inherited from a class in `pt/*testcase` 
directory.
6. The example:
`suites/features/test_new_features.py`
```python
from tiden.case.generaltestcase import GeneralTestCase
from tiden import attr

class TestNewFeatures (GeneralTestCase):
    def setup(self):
        super().setup()
        
    def teardown(self):
        pass
        
    @attr('simple_test', 'new')
    def test_feature_1(self):
      a = 1
      b = 1
      assert a == b, 'test a == b'
```


## 5. Reports

The tool provides XUnit report in `var` directory.

## 6. The key execution stages:
1. Construct the test configuration file and store it in 
`var/<suite_name>-<timestamp>` directory
2. Copy (and repack if required) the artifacts in `var/artifacts`
directory.
3. Check connection to remote hosts
4. Kill all java processes and clean up `environment.home` directory 
if `--clean=all` passed
5. Deploy artifacts on remote hosts and unzip them
6. Iterate over test modules (if more that one found). 
Repeat 7-11 for every test module.
7. Execute `setup()` method from the test class (if exists).
8. Deploy test class resource directory (if exists) on remote hosts.
9. Iterate over (filtered) test class methods
10. Execute `teardown()` method from test class (if exists)
11. Collect log files on remote hosts and download them 
as `<ip_address>_logs.zip` in 
`var/<suite_name>-<timestamp>/<test_module_name>` directory 
12. Store report files in `var` directory

## 7. Local directory structure

* `<var_dir>/artifacts` - directory for artifacts found in 
`artifacts` key of test configuration

* `<var_dir>/<suite_name>-<timestamp>` - suite work directory
 
* `<var_dir>/<suite_name>-<timestamp>/tmp` - suite tmp directory
 
* `<var_dir>/<suite_name>-<timestamp>/<test_module_name>` - 
test module directory
 
* `<var_dir>/<suite_name>-<timestamp>/<test_module_name>/res` - 
test module resource directory

## 8. Remote directory structure

* `<environment.home>/artifacts` - directory for artifacts

* `<environment.home>/<suite_name>-<timestamp>` - suite work directory

* `<environment.home>/<suite_name>-<timestamp>/<artifact_name_1>` - 
artifact directory if set `artifacts.<artifact_name>.remote_unzip: true` in the test configuration

* `<environment.home>/<suite_name>-<timestamp>/<test_module_name>` - 
test module work directory, resource copied here

* `<environment.home>/<suite_name>-<timestamp>/<test_module_name>/<TestClass>` - 
test class work directory
 
* `<environment.home>/<suite_name>-<timestamp>/<test_module_name>/<TestClass>/setup` - 
test class setup work directory
 
* `<environment.home>/<suite_name>-<timestamp>/<test_module_name>/<TestClass>/teardown` - 
test class teardown work directory
 
* `<environment.home>/<suite_name>-<timestamp>/<test_module_name>/<TestClass>/<test_method_name>`- 
test class method work directory
 

## 9. The useful test configuration keys
 
* `artifacts.<artifact_name>.remote_unzip: true`
Unzip the artifact archive on remote hosts after deployment.

* `artifacts.<artifact_name>.repack: <command list>`
Repack the artifact archive and reduce the size for deployment. 
The options supports the following commands:
    * `move self:<path1> self:</path2>` - move directory `<path1>` 
    in `<path2>`
    * `copy self:<path1> self:</path2>` - copy directory `<path1>` 
    in `<path2>`
    * `copy $<artifact_name>$<path1> self:</path2>` - copy other artifact by name `$<artifact_name>$` or separate files from specific path in other artifact `$<artifact_name>$<path1>` in `</path2>`  
    * `delete self:<path1>` - delete `<path>`

By default newly founded artifacts will upload on remote hosts or replaced. All changed artifacts will be automatically redeployed

* `connection_mode: [paramiko|ansible|local]`
The way to connect to remote hosts. Python `paramiko` is by default. 
Use `ansible` if the deployment is large.
Use `local` to turn tiden into local testing framework, in that case all `[server|client|common]_hosts` in 
environment configuration must start with '127.0' network.

* `ignite`: dictionary with default options for Ignite deployments.
    * `bind_to_host: True|False`
    Defaults to False, unless `connection_mode` is local, True otherwise.
    If `bind_to_host` is True, grid config files are patched to tie each node to its host 
    via `IgniteConfiguration.localHost` property.
    
    * `unique_node_ports: True|False`
    Defaults to False, unless `connection_mode` is local, True otherwise.
    If `unique_node_ports` is True, grid config files are patched to tie each node' `TcpCommunicationSpi` to
    specfic port number unique for all grid nodes (e.g. there would be no node with equal 
    `TcpCommunicationSpi.port` property in the grid).

* `environment.client_jvm_options: <list>` 
The list of JVM options passed to client nodes.

* `environment.env_vars: <dictionary>`
The dictionary of remote host environment variables, where key is a 
variable name. Also the value can be read from an another environment 
variable: `<variable_name>:$<another_variable_name>`

* `environment.server_jvm_options: <list>`
The list of JVM options passed to server nodes.

* `xunit_file: <filename>`
The name of file with test report in xUnit format. The report file with given name will be created in 
the `var_dir` directory. Optional, defaults to 'xunit.xml'.  

* `testrail_report: <filename>`
The name of file with test report in GG QA `testrail-report.py` utility format.  
The report file with given name will be created in the `var_dir` directory. 
Optional, defaults to 'testrail_report.yaml'.

* `repeated_test` or `repeated_test.<attr_name>`
When given `--to=repeated_test=N`, executes all tests otherwise matched by `--attr` in all suites matched by `--ts` 
at most N number of iterations or until first test failure.

When given `--to=repeated_test.<testattr>=N`, executes only tests matched by `<testattr>` at most N number of 
iterations or until first failure, all other test remains executed as usual. 
  

## 10. Decorators

* attribute `@attr('<attr_name_1>', '<attr_name_2>', ...)`

```python
...
    @attr('simple_test', 'new')
    def test_1(self):
        pass
```
_Note: The name of test method always added to attributes list._

* fixture `@with_setup('<method_name>', '<method_name>')`

```python
...
    def before_test(self):
        pass
    def after_test(self):
        pass            
    @with_setup('before_test', 'after_test')
    def test_1(self):
        pass
```

* unconditional skip `@skip('<the_reason>')` 

```python
...
    @skip('issue BUG12345')
    def test_1(self):
        pass
```

* conditional skip `@require(<requirements>)`. 

_Note: All requirements must be met for test to run._

Supported requirements:
 
  - `min_ignite_version` = `<version string>`
  - `min_server_nodes` = `<number of server nodes>`
  - `min_client_nodes` = `<number of client nodes>`


```python
from tiden.util import require
...
    @require(min_server_nodes=4, min_ignite_version='2.4.2-p4')
    def test_2(self):
        pass

```

Unnamed arguments to `@require` are evaluated during test compilation, any False result will lead to test skip,
which allows following example usage as well:

```python
from tiden.testconfig import test_config
from tiden.util import require

...
    @require(test_config.ignite.pitr_enabled)
    def test():
        pass

```  

* explicit repeated iterations `@repeated_test(<N>)` or `@repeate_test(<N>, test_names=[<test_names>])`. 

```python
from tiden.util import repeated_test

...
    @repeated_test(3)
    def test():
        pass

```  

Makes given test run at most N times or until first failure. Each successive test iteration would have its own variable 
directory suffixed by iteration number. 

When test fails, its name will be renamed in report file to `<test_name>_iteration_<M>`, where `M` is failed iteration number. 


## 11. Contributing 

The test framework encompasses unit-tests for self-testing misc functionality. 
Feel free to contribute at will, but ensure unit-tests remain stable. 
It is desired that contributor provided unit-tests for added functionality.

Running unit tests requires installed `py.test` dependency.

Example:

```bash
    py.test tests -x --tb=long  
```  
