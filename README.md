# Otter

The Otter is a small command-line tool that helps to maintain and analyze solutions based on **SAP HANA Extended Application Services Advanced Model** (XS Advanced / XSA). 

The Otter implements reusable modules representing XS Advanced Controller and its entities, e.g., applications, service instances, user-provided service instances and others. Technically, the tool acts as an HTTP client utilizing Cloud Foundry-like APIs of XS Advanced Controller.

The main objectives of the development are:

* To simplify collection of the aggregated information about XS Advanced entities (organizations, spaces, applications, service instances, etc.)
* To simplify collection of applications' API logs (the logs of the Platform Router containing statistics of HTTP requests processing)
* To simplify collection of the user-related information, e.g., the assignment of Role Collections to users, the assignment of Controller Roles to users, etc.
* To simplify some chosen routine operations, e.g., deletion of the post-mortem (STOPPED and CRASHED) application instances
* To provide reusable modules that can be used in the automation tasks



## Table of Contents
- [Important Notes](#important-notes)
- [Deployment](#deployment)
  - [Environment requirements](#environment-requirements)
  - [Packaging](#packaging)
  - [Target System Requirements](#target-system-requirements)
- [Usage](#usage)
  - [Client Configuration](#client-configuration)
    - [Section `client_config`](#section-client_config)
    - [Section `controller_config`](#section-controller_config)
    - [Section `operations`](#section-operations)
  - [General syntax](#general-syntax)
  - [Required connection arguments](#required-connection-arguments)
      - [Argument `-a, --api-endpoint <API_ENDPOINT>`](#argument--a---api-endpoint-api_endpoint)
      - [Argument `-u, --username <USER>`](#argument--u---username-user)
      - [Argument `-p, --password <PASSWORD>`](#argument--p---password-password)
      - [Argument `-o, --organization <ORGANIZATION>`](#argument--o---organization-organization)
      - [Example usage of required arguments:](#example-usage-of-required-arguments)
  - [Optional selective arguments](#optional-selective-arguments)
      - [Argument  `-s, --space <SPACE>`](#argument---s---space-space)
      - [Argument `-app, --application <APPLICATION>`](#argument--app---application-application)
      - [Argument  `-exclist, --exclusion-list-name <EXCLUSION_LIST>`](#argument---exclist---exclusion-list-name-exclusion_list)
  - [Operation arguments](#operation-arguments)
      - [Argument  `-rdb`, `--report-databases`](#argument---rdb---report-databases)
      - [Argument  `-rii`, `--report-invalid-instances`](#argument---rii---report-invalid-instances)
      - [Argument `-rora`, `--report-org-roles-assignment`](#argument--rora---report-org-roles-assignment)
      - [Argument `-rsra`, `--report-space-roles-assignment`](#argument--rsra---report-space-roles-assignment)
      - [Argument `-rrca`, `--report-role-collections-assignment`](#argument--rrca---report-role-collections-assignment)
      - [Argument `-rai`, `--report-application-instances`](#argument--rai---report-application-instances)
      - [Argument `-rsi`, `--report-service-instances`](#argument--rsi---report-service-instances)
      - [Argument `-rupsi`, `--report-user-provided-service-instances`](#argument--rupsi---report-user-provided-service-instances)
      - [Argument `-rsk`, `--report-service-keys`](#argument--rsk---report-service-keys)
      - [Argument `-rca`, `--report-crashing-apps`](#argument--rca---report-crashing-apps)
      - [Argument `-rnmo`, `--report-non-mta-objects`](#argument--rnmo---report-non-mta-objects)
      - [Argument `-rpal`, `--report-parsed-app-log`](#argument--rpal---report-parsed-app-log)
      - [Argument `-sca`, `--stop-crashing-apps`](#argument--sca---stop-crashing-apps)
      - [Argument `-dscai`, `--delete-stopped-crashed-app-instances`](#argument--dscai---delete-stopped-crashed-app-instances)
      - [Argument `-dnmasi`, `--delete-non-mta-apps-and-service-instances`](#argument--dnmasi---delete-non-mta-apps-and-service-instances)
- [Obtain Support](#obtain-support)


## Important Notes

While using the tool, please consider following important notes:

> The project is not the official software released by SAP. Hence no official support can be assumed from SAP concerning the tool and the implemented functionality.

> The project is released under Apache License, v2.0. Therefore, please consider it as provided on an AS IS basis without warranties or conditions of any kind. Use functions modifying state of the system carefully, e.g., applications or service instances deletion.

> Please read the documentation about the functions carefully. In case of the bugs, malfunctions or feature requests, please raise an [Issue](https://github.com/nklinked/otter/issues/new/choose) in the repository.



## Deployment

### Environment requirements

The tool is written and tested with Python 3.9.4. The tool is dependent on following packages:

| Package  | Version | Purpose                                                  |
| -------- | ------- | -------------------------------------------------------- |
| argparse | 1.4.0   | Handles command line arguments                           |
| pandas   | 1.3.2   | Operates with DataFrames and produce CSV files output    |
| pathlib  | 1.0.1   | Operates with relative file paths                        |
| PyYAML   | 5.4.1   | Parses the configuration files                           |
| requests | 2.26.0  | Implements the main HTTP client functionality            |
| urllib3  | 1.26.6  | Supports implementation of the HTTP client functionality |

Provided dependencies are listed in the `/requirements.txt` .



### Packaging

The tool can run from the source codes in the respective Python environment with the required packages installed. 

The tool can also be packaged into a single executable file that will contain the Python runtime and required packages for a target platform. The package  `Pyinstaller` can be used for that purpose, e.g.,  running `pyinstaller --onefile otter.py`.



### Target System Requirements

The tool was developed and tested with SAP HANA Extended Application Services Advanced Model >= 1.0.132.

The tool requires an XS Advanced user with Controller User and Administrator privileges. Usually those privileges are delivered by standard SAP Role Collections: `XS_CONTROLLER_USER` and `XS_CONTROLLER_ADMIN`. The user can be created using SAP XS CLI:

```shell
xs create-user <USER> <PASSWORD> --no-password-change --platform
xs assign-role-collection XS_CONTROLLER_USER <USER>
xs assign-role-collection XS_CONTROLLER_ADMIN <USER>
```

Please consider granting the user with the SpaceDeveloper role in spaces where modifications are required.



## Usage

> Please review the client configuration and the Exclusion List Concept to configure the tool properly.

> Please provide a proper name of the organization in the **DEFAULT** exclusion list to avoid deleting the standard applications.

General configuration flow:

* Prepare the environment. Optionally package the tool using the `Pyinstaller`

* Review the documentation
* Configure the DEFAULT exclusion list in `config.yaml`
* Run the required commands



### Client Configuration

The configuration of the tool is stored in the `config.yaml`. The file should be located in the same directory as the executable file. The default configuration is provided below:

```yaml
client_config:
  output_dir: ./output
  logging_level: INFO # CRITICAL | ERROR | WARNING | INFO | DEBUG | NOTSET

controller_config:
  enable_experimental_features: True

operations:
  exclusion_list:
    DEFAULT:
      orgs:
        orgname:
          spaces:
            SAP:
              allow_operations: False

# The template of section operations
#operations:
#  exclusion_list:
#    DEFAULT:  # The existence of list DEFAULT is mandatory
#      orgs:
#        your_organization_name:
#          spaces:
#            SAP: # Always keep space SAP in your lists to avoid unexpected operations on standard apps
#              allow_operations: False
#            YOUR_CUSTOM_SPACE_NAME:
#              allow_operations: True
#              apps:
#                - custom-app-name-a
#                - custom-app-name-b
#                - custom-app-name-c
#              service_instances:
#                - custom-service-name-a
#                - custom-service-name-b
#                - custom-service-name-c
```

#### Section `client_config`

* Property `output_dir` allows to configure the output directory to store the collected CSV files and logs.
* Property `logging_level` specifies the logging level applied to the modules. Level DEBUG produces a highly granular and excessive logs. The default logging level is INFO.

#### Section `controller_config`

* Property `enable_experimental_features` allows to restrict operations modifying the state of the system. Having the value `False`, the tool will not run any operation that may influence state of applications or service instances.

#### Section `operations`

This section is primarily used to implement the Exclusion List definitions. The Exclusion List is technically a description of organizations, their spaces, applications and service instances that should be **excluded from any operation, that may modify their state**.  Such operations will require the Exclusion List name to be given as an argument to run.

The Exclusion Lists have no influence on the reports collecting the information.

Please see the comments in the YAML definition below for details about the functionality.

```yaml
operations:
  exclusion_list:  # [DO NOT CHANGE] Definition of Exclusion Lists
    DEFAULT:       # Name of the default Exclusion List. The existence of list DEFAULT is mandatory
      orgs:        # [DO NOT CHANGE] Defintion of organizations
        orgname:   # Name of the organization
          spaces:  # [DO NOT CHANGE] Definition of spaces
            SAP:   # Name of the space
              allow_operations: False # Are the operations generally allowed?
    MY_CUSTOM_LIST: # Name of another custom Exclusion List
      orgs:         # [DO NOT CHANGE] Defintion of organizations
        MY_ORGNAME: # Name of my own organization
          spaces:   # [DO NOT CHANGE] Definition of spaces
            SAP:    # Name of the space. Always exclude space SAP from the operations!
              allow_operations: False # Are the operations generally allowed?
            MY_CUSTOM_SPACE_NAME:     # Name of my own space
              allow_operations: True  # Are the operations generally allowed?
              apps:  # [DO NOT CHANGE] Definition of apps
                - custom-app-name-a   # Name of my own application A
                - custom-app-name-b   # Name of my own application B
                - custom-app-name-c   # Name of my own application C
              service_instances:      # [DO NOT CHANGE] Definition of service instances
                - custom-service-name-a  # Name of my own service instance A
                - custom-service-name-b  # Name of my own service instance B
                - custom-service-name-c  # Name of my own service instance C
```



### General syntax

Please find the general command line syntax below.

```sh
otter -a <API_ENDPOINT> -u <USER> -p <PASSWORD> -o <ORGANIZATION> [-s, --space <SPACE>] [-rdb, --report-databases] [-rii, --report-invalid-instances] [-rora, --report-org-roles-assignment] [-rsra, --report-space-roles-assignment] [-rrca, --report-role-collections-assignment] [-rai, --report-application-instances] [-rsi, --report-service-instances] [-rsk, --report-service-keys] [-rca, --report-crashing-apps] [-rnmo, --report-non-mta-objects] [-app, --application <APPLICATION>] [-rpal, --report-parsed-app-log] [-exclist, --exclusion-list-name <EXCLUSION_LIST>] [-sca, --stop-crashing-apps] [-dscai, --delete-stopped-crashed-app-instances] [-dnmasi, --delete-non-mta-apps-and-service-instances]
```



### Required connection arguments

Running any command or a set of commands you must provide the information about the XS Controller API Endpoint, credentials (user and password) and the target XS Advanced organization. Running simultaneous operations in multiple organizations is not supported at the moment.



##### Argument `-a, --api-endpoint <API_ENDPOINT>` 

The given value represents the XS Advanced Controller Endpoint

------

##### Argument `-u, --username <USER>`

The given value represents the User

------

##### Argument `-p, --password <PASSWORD>`

The given value represents the Password

------

##### Argument `-o, --organization <ORGANIZATION>`

The given value represents the name of the target Organization

------

##### Example usage of required arguments: 

```sh
otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org
```

> Such a command does not produce any result since no instruction is given about the required reports or operations



### Optional selective arguments

Additional arguments can be passed to limit the scope of operations, e.g., collect the data from the given space or application.



##### Argument  `-s, --space <SPACE>`

The given value represents the name of the target Space. The argument restricts operations to the given space. In case no argument value is provided, operations are performed on all spaces within the given organization.

The argument is effective in a combination with following operations: `[-rai, --report-application-instances] [-rsi, --report-service-instances] [-rsk, --report-service-keys] [-rca, --report-crashing-apps] [-rnmo, --report-non-mta-objects] [-app, --application <APPLICATION>] [-rpal, --report-parsed-app-log] [-exclist, --exclusion-list-name <EXCLUSION_LIST>] [-sca, --stop-crashing-apps] [-dscai, --delete-stopped-crashed-app-instances] [-dnmasi, --delete-non-mta-apps-and-service-instances]`.

Example usage of the argument:

* To perform the operation only in the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space [--operation]
  ```

* To perform the operation in all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org [--operation]
  ```



------

##### Argument `-app, --application <APPLICATION>`

The given value represents the name of the target Application. The argument restricts operations to the given application. In case no argument value is provided, operations are performed on all applications within the given space.

The argument requires  `-s`, `--space` to be provided. The argument is effective in a combination with following operations: `[-rpal, --report-parsed-app-log]`.

Example usage of the argument:

* To perform the operation only for the given application:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -app app_name [--report-parsed-app-log]
  ```

* To perform the operation for all applications within the space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space [--report-parsed-app-log]
  ```



------

##### Argument  `-exclist, --exclusion-list-name <EXCLUSION_LIST>`

The given value represents the name of the Exclusion List configured in the `config.yaml`. The argument restricts operations on entities configured in the Exclusion List, e.g., prohibited spaces, application or service instances.

In case no argument value is provided, the Exclusion List with name `DEFAULT` is used from the `config.yaml`.

The argument must be provided to run following operations: `[-sca, --stop-crashing-apps] [-dscai, --delete-stopped-crashed-app-instances] [-dnmasi, --delete-non-mta-apps-and-service-instances]`.

Example usage of the argument:

* To perform the operation only for the given application:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -app app_name [--report-parsed-app-log]
  ```

* To perform the operation for all applications within the space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space [--report-parsed-app-log]
  ```



### Operation arguments

Generally all operations belong to two classes: operations collecting the data and operations modifying the state of the system.



##### Argument  `-rdb`, `--report-databases`

Having the argument given, the information about database tenants known by XS Advanced will be collected in the CSV file. 

The produced output will contain following fields: `GUID`, `Tenant`, `Encryption`, `HANA Broker User`, `HANA Broker Schema`, `Mapped Orgs / Spaces`, `DB Usergroups`, `JDBC Endpoint`.

The operation is the system wide and ignores any selective argument.

The resulting CSV file will be stored in `<output_dir>/databases/databases.csv`

Example usage of the argument:

```sh
otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rdb
```



------

##### Argument  `-rii`, `--report-invalid-instances`

Having the argument given, the information about inconsistent HANA service instances known by HANA Broker will be collected in the CSV file. Example of the inconsistent service instance is the one that is known by the XS Advanced but missing the container schemas in the database.

The produced output will contain following fields: `Tenant Name`, `Org GUID`, `Org Name`, `Space GUID`, `Space Name`, `Service Instance GUID`, `Service Instance Name`, `Created At`, `Updated At`, `Last Operation Type`, `Last Operation State`, `Last Operation Time`, `Service Label`, `Service Plan Name`, `Parameters`, `Belongs to HANA Broker`, `Tenant Name (for HANA)`, `Container Schema (for HANA)`, `Error Message`.

The operation is the system wide and ignores any selective argument.

The resulting CSV file will be stored in `<output_dir>/databases/invalid_instances.csv`

Example usage of the argument:

```sh
otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rii
```



------

##### Argument `-rora`, `--report-org-roles-assignment`

Having the argument given, the information about Organization roles (OrgManager, OrgAuditor) assigned to users will be collected in the CSV file.

The produced output will contain following fields: `User GUID`, `User UAA GUID`, `User Name`, `Origin`, `Is Active`, `Is Orphaned`, `Organization GUID`, `Organization Name`, `Role`.

The operation is the system wide and ignores any selective argument.

The resulting CSV file will be stored in `<output_dir>/users/org_roles_assignment.csv`

Example usage of the argument:

```sh
otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rora
```



------

##### Argument `-rsra`, `--report-space-roles-assignment`

Having the argument given, the information about Space roles (SpaceManager, SpaceAuditor, SpaceDeveloper) assigned to users will be collected in the CSV file.

The produced output will contain following fields: `User GUID`, `User UAA GUID`, `User Name`, `Origin`, `Is Active`, `Is Orphaned`, `Organization GUID`, `Organization Name`, `Space GUID`, `Space Name`,  `Role`.

The operation is the system wide and ignores any selective argument.

The resulting CSV file will be stored in `<output_dir>/users/space_roles_assignment.csv`

Example usage of the argument:

```sh
otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rsra
```



------

##### Argument `-rrca`, `--report-role-collections-assignment`

Having the argument given, the information about Space roles (SpaceManager, SpaceAuditor, SpaceDeveloper) assigned to users will be collected in the CSV file.

The produced output will contain following fields: `User GUID`, `User UAA GUID`, `User Name`, `Origin`, `Is Active`, `Is Orphaned`, `Role Collection Name`.

The operation is the system wide and ignores any selective argument.

The resulting CSV file will be stored in `<output_dir>/users/role_collections_assignment.csv`

Example usage of the argument:

```sh
otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rrca
```



------

##### Argument `-rai`, `--report-application-instances`

Having the argument given, the detailed information about applications will be collected in the CSV file.

The produced output will contain following fields: `Org GUID`, `Org Name`, `Space GUID`, `Space Name`, `App GUID`, `App Name`, `Target Runtime`, `Detected Buildpack`, `Created At`, `Updated At`, `State`, `Is Down`, `Uptime *100%`, `Memory`, `MTA Module Name`, `MTA ID`, `MTA Version`, `MTA Module Dependencies`, `MTA Services`, `Count of Bindings`, `Target Container (hdi-deploy)`, `Belongs to MTA`, `Has Deployment Tasks`, `Is HDI Deployer`, `Planned Instances Count`, `Running Instances Count`, `Crashed Instances Count`, `Short-Term Crashes Count`, `Mid-Term Crashes Count`, `Long-Term Crashes Count`, `Instance GUID`, `Instance Droplet GUID`, `Instance Started At`, `Instance Created At`, `Instance Updated At`, `Instance State`, `Instance Failure Reason`, `Instance PID`, `Instance OS User`.

The operation can be limited to a single space by providing argument  `-s, --space <SPACE>`. In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

The resulting CSV file will be stored in `<output_dir>/apps/<org>/<space>/apps.csv`

Example usage of the argument:

* To collect information only for the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -rai
  ```

* To collect information for all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rai
  ```



------

##### Argument `-rsi`, `--report-service-instances`

Having the argument given, the detailed information about service instances will be collected in the CSV file.

The produced output will contain following fields: `Org GUID`, `Org Name`, `Space GUID`, `Space Name`, `Service Instance GUID`, `Service Instance Name`, `Created At`, `Updated At`, `Last Operation Type`, `Last Operation State`, `Last Operation Time`, `Service Label`, `Service Plan Name`, `Parameters`, `Belongs to HANA Broker`, `Tenant Name (for HANA)`, `Container Schema (for HANA)`, `Bindings Count`, `Bindings to Apps Count`, `Bindings to MTAs Count (except di-builder)`, `References to MTAs Count (except di-builder)`, `Bindings to di-builder Count`, `Bindings to Standalone Apps Count`, `Service Keys Count`.

The operation can be limited to a single space by providing argument  `-s, --space <SPACE>`. In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

The resulting CSV file will be stored in `<output_dir>/services/<org>/<space>/service_instances.csv`

Example usage of the argument:

* To collect information only for the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -rsi
  ```

* To collect information for all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rsi
  ```



------

##### Argument `-rupsi`, `--report-user-provided-service-instances`

Having the argument given, the detailed information about user-provided service instances will be collected in the CSV file.

The produced output will contain following fields: `Org GUID`, `Org Name`, `Space GUID`, `Space Name`, `UPS Instance GUID`, `UPS Instance Name`, `Created At`, `Updated At`, `Last Operation Type`, `Last Operation State`, `Credentials (JSON)`.

The operation can be limited to a single space by providing argument  `-s, --space <SPACE>`. In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

The resulting CSV file will be stored in `<output_dir>/services/<org>/<space>/user_provided_service_instances.csv`

Example usage of the argument:

* To collect information only for the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -rupsi
  ```

* To collect information for all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rupsi
  ```



------

##### Argument `-rsk`, `--report-service-keys`

Having the argument given, the detailed information about service instances and keys will be collected in the CSV file.

The produced output will contain following fields: `Org GUID`, `Org Name`, `Space GUID`, `Space Name`, `Service Instance GUID`, `Service Instance Name`, `Created At`, `Updated At`, `Last Operation Type`, `Last Operation State`, `Last Operation Time`, `Service Label`, `Service Plan Name`, `Parameters`, `Belongs to HANA Broker`, `Tenant Name (for HANA)`, `Container Schema (for HANA)`, `Service Key GUID`, `Service Key Name`, `Service Key Created At`, `Service Key Updated At`.

The operation can be limited to a single space by providing argument  `-s, --space <SPACE>`. In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

The resulting CSV file will be stored in `<output_dir>/services/<org>/<space>/service_instance_keys.csv`

Example usage of the argument:

* To collect information only for the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -rsk
  ```

* To collect information for all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rsk
  ```



------

##### Argument `-rca`, `--report-crashing-apps`

Having the argument given, the detailed information about continuously crashing applications will be collected in the CSV file. The application is assumed as continuously crashing after 3 crashes or after 1 crash in a short term and 10 crashes in a midterm that is treated as a critical threshold.

The produced output will contain following fields: `Org GUID`, `Org Name`, `Space GUID`, `Space Name`, `App GUID`, `App Name`, `Target Runtime`, `Detected Buildpack`, `Created At`, `Updated At`, `State`, `Is Down`, `Uptime *100%`, `Memory`, `MTA Module Name`, `MTA ID`, `MTA Version`, `MTA Module Dependencies`, `MTA Services`, `Count of Bindings`, `Target Container (hdi-deploy)`, `Belongs to MTA`, `Has Deployment Tasks`, `Is HDI Deployer`, `Planned Instances Count`, `Running Instances Count`, `Crashed Instances Count`, `Short-Term Crashes Count`, `Mid-Term Crashes Count`, `Long-Term Crashes Count`, `Instance GUID`, `Instance Droplet GUID`, `Instance Started At`, `Instance Created At`, `Instance Updated At`, `Instance State`, `Instance Failure Reason`, `Instance PID`, `Instance OS User`.

The operation can be limited to a single space by providing argument  `-s, --space <SPACE>`. In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

The resulting CSV file will be stored in `<output_dir>/apps/<org>/<space>/continously_crashing_apps.csv`

Example usage of the argument:

* To collect information only for the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -rca
  ```

* To collect information for all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rca
  ```



------

##### Argument `-rnmo`, `--report-non-mta-objects`

Having the argument given, the detailed information about applications and service instances, having no MTA information will be collected in the CSV file.  Most frequently applications and service instances having no Multi-Target Application attribution are created by the SAP Web IDE and are not cleaned up properly after the development. The possible exception is the applications `pushed` to XS Advanced spaces instead of deployment via `deploy-service`.

The produced outputs will contain the same fields as `-rai` (`--report-application-instances`) and `-rsi` (`--report-service-instances`).

The operation can be limited to a single space by providing argument `-s, --space <SPACE>`. In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

The resulting CSV files will be stored in `<output_dir>/apps/<org>/<space>/non_mta_apps.csv` and in  `<output_dir>/services/<org>/<space>/non_mta_service_instances.csv` 

Example usage of the argument:

* To collect information only for the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -rnmo
  ```

* To collect information for all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rnmo
  ```



------

##### Argument `-rpal`, `--report-parsed-app-log`

Having the argument given, the parsed application log, having only RTR entries,  will be stored in the CSV file. Such an application log contains only the entries representing the API call routed to the application. The log is useful to identify the long running API calls within the monitored timeframe.

The produced output will contain following fields: `Timestamp`, `Caller`, `Calle`, `Method`, `Request String`, `HTTP Status`, `Response Size, byte`, `Response Time, ms`.

The operation can be limited to a single app by providing argument `-app, --application <APPLICATION>` coupled with argument `-s, --space <SPACE>` . 

The operation can be limited to a single space as well by providing argument `-s, --space <SPACE>` . In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

The resulting CSV files will be stored in `<output_dir>/apps/<org>/<space>/<app>/router_log.csv`

Example usage of the argument:

* To collect information only for the given application:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -app some_app -rpal
  ```

* To collect information for all applications within the given space and organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -rpal
  ```

* To collect information for all applications in all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -rnmo
  ```



------

##### Argument `-sca`, `--stop-crashing-apps`

> This operation changes the state of the system.
>
> The operation is experimental and requires the flag `enable_experimental_features` to be  `True` in the `config.yaml`.
>
> The operation requires the exclusion list to be consciously provided. If no exclusion list is specified the exclusion list with name `DEFAULT` is used from the `config.yaml`.

Having the argument given, the applications identified as continuously crashing will be stopped. The application is assumed as continuously crashing after 3 crashes or after 1 crash in a short term and 10 crashes in a midterm that is treated as a critical threshold.

It is recommended to review the report generated by `-rca` (`--report-crashing-apps`) and ensure that the exclusion list remains in the actual state in the `config.yaml` prior to running the operation.

The operation can be limited to a single space by providing argument `-s, --space <SPACE>`. In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

Example usage of the argument:

* To perform the operation only in the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -sca
  ```

* To perform the operation in all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -sca
  ```



------

##### Argument `-dscai`, `--delete-stopped-crashed-app-instances`

> This operation changes the state of the system.
>
> The operation is experimental and requires the flag `enable_experimental_features` to be  `True` in the `config.yaml`.
>
> The operation requires the exclusion list to be consciously provided. If no exclusion list is specified the exclusion list with name `DEFAULT` is used from the `config.yaml`.

Having the argument given, the application instances in states STOPPED and CRASHED will be deleted.

It is recommended to review the report generated by `-rai` (`--report-application-instances`) and ensure that the exclusion list remains in the actual state in the `config.yaml` prior to running the operation.

The operation can be limited to a single space by providing argument `-s, --space <SPACE>`. In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

Example usage of the argument:

* To perform the operation only in the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -dscai
  ```

* To perform the operation in all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -dscai
  ```



------

##### Argument `-dnmasi`, `--delete-non-mta-apps-and-service-instances`

> **Between other commands this one is the most sensitive and potentially dangerous.** 
>
> This operation changes the state of the system.
>
> The operation is experimental and requires the flag `enable_experimental_features` to be  `True` in the `config.yaml`.
>
> The operation requires the exclusion list to be consciously provided. If no exclusion list is specified the exclusion list with name `DEFAULT` is used from the `config.yaml`. In case the exclusion list is not maintained properly the **DATA LOSS IS POSSIBLE**. 
>
> 

Having the argument given, applications and service instances, having no MTA information will be deleted.  The requirement for such a scenario is based on the actively used development systems where the development containers and applications are intensively produced by the SAP Web IDE. Those objects keep remaining in the system once development stops and should be deleted manually.

Before running this operation you **must** review the report generated by `-rnmo`,(`--report-non-mta-objects`) and ensure that your exclusion list  in the `config.yaml`  contains all objects that should be kept in the system. This requirement is mandatory because of the following exceptions, that cannot be handled technically:

* **The space `SAP` containing standard applications must be always excluded from this operation!** Some of the standard XS Advanced applications do not have the MTA metadata provided and deletion of them will bring the system into a non-functional state.
* Pushed (not deployed) applications may have no MTA metadata provided. If these apps are not added into the exclusion list they will be identified as orphaned and deleted
* Manually created service instances, e.g., UAA service instances and Jobscheduler instances created outside of the project, will be identified as orphaned and deleted
* The HDI (HANA) service instances demonstrating the extremely high deletion time may fail to delete. In case you know such HDI service instances, it is recommended to add them into the Exclusion List and delete them manually with `XS CLI` or with `HDI APIs` and then with `XS CLI`

User-provided Service Instances are not valid for this scenario and will remain untouched

The operation can be limited to a single space by providing argument `-s, --space <SPACE>`. In case argument `-s, --space <SPACE>` is not given the command will be executed for all spaces within the given organization.

Example usage of the argument:

* To perform the operation only in the given space:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -s some_space -dnmasi
  ```

* To perform the operation in all spaces within the given organization:

  ```sh
  otter -a https://some.hostname:30033 -u some_user -p SomePassword12 -o some_org -dnmasi
  ```



## Obtain Support

In case of the bugs, malfunctions or feature requests, please raise an [Issue](https://github.com/nklinked/otter/issues/new/choose) in the repository.
