import logging
import pandas as pd
from components.controller.service import ServiceInstance, ServiceKey, UserProvidedServiceInstance # pylint: disable=import-error
# pylint: disable=import-error
from components.controller.application import Application, ApplicationInstance, ApplicationLogs
from components.controller.database import Database # pylint: disable=import-error
from components.controller.controller import User # pylint: disable=import-error


class Collector:
    # pylint: disable=too-many-public-methods

    def __init__(self, controller, client):
        self.controller = controller
        self.client = client

    def get_objects_from_exclusion_list(self, **kwargs):
        # List DEFAULT must be always provided in config.yaml
        kwargs.setdefault('exclusion_list_name', 'DEFAULT')
        exclusion_list_name = (kwargs.get('exclusion_list_name')
                               if kwargs.get('exclusion_list_name')
                               else 'DEFAULT')
        try:
            excluded_objects = self.client.config.get('operations').get('exclusion_list').get(
                exclusion_list_name)
        except Exception as e: # pylint: disable=invalid-name
            logging.error(f'Failed to load objects from exclusion list {exclusion_list_name}',
                          exc_info=e)
            raise
        else:
            return excluded_objects

    def get_excluded_space_guids(self, **kwargs):
        exclusion_list = self.get_objects_from_exclusion_list(**kwargs)
        excluded_space_guids = []
        if exclusion_list:
            excluded_orgs = exclusion_list.get('orgs')
            if excluded_orgs:
                for org_name in excluded_orgs:
                    org = self.controller.get_org_by_name(org_name)
                    if org:
                        excluded_spaces = excluded_orgs[org_name].get('spaces')
                        if excluded_spaces:
                            for space_name in excluded_spaces:
                                allow_operations = excluded_spaces[space_name].get(
                                    'allow_operations')
                                if not allow_operations:
                                    space = org.get_space_by_name(space_name)
                                    if space:
                                        excluded_space_guids.append(space.guid)
        return excluded_space_guids

    def get_excluded_app_guids(self, **kwargs):
        exclusion_list = self.get_objects_from_exclusion_list(**kwargs)
        excluded_app_guids = []
        if exclusion_list:
            excluded_orgs = exclusion_list.get('orgs')
            if excluded_orgs:
                for org_name in excluded_orgs:
                    org = self.controller.get_org_by_name(org_name)
                    if org:
                        excluded_spaces = excluded_orgs[org_name].get('spaces')
                        if excluded_spaces:
                            for space_name in excluded_spaces:
                                space = org.get_space_by_name(space_name)
                                if space:
                                    allow_operations = excluded_spaces[space_name].get(
                                        'allow_operations')
                                    if allow_operations:
                                        excluded_apps = excluded_spaces[space_name].get(
                                            'apps')
                                        if excluded_apps:
                                            for app_name in excluded_apps:
                                                app = space.get_app_by_name(app_name)
                                                if app:
                                                    excluded_app_guids.append(app.guid)
                                    else:
                                        excluded_app_guids = (excluded_app_guids
                                                              + list(space.apps.keys()))
        return excluded_app_guids

    def get_excluded_service_instance_guids(self, **kwargs):
        # pylint: disable=line-too-long
        exclusion_list = self.get_objects_from_exclusion_list(**kwargs)
        excluded_service_instance_guids = []
        if exclusion_list:
            excluded_orgs = exclusion_list.get('orgs')
            if excluded_orgs:
                for org_name in excluded_orgs:
                    org = self.controller.get_org_by_name(org_name)
                    if org:
                        excluded_spaces = excluded_orgs[org_name].get('spaces')
                        if excluded_spaces:
                            for space_name in excluded_spaces:
                                space = org.get_space_by_name(space_name)
                                if space:
                                    allow_operations = excluded_spaces[space_name].get(
                                        'allow_operations')
                                    if allow_operations:
                                        excluded_service_instances = excluded_spaces[space_name].get(
                                            'service_instances')
                                        if excluded_service_instances:
                                            for service_instance_name in excluded_service_instances:
                                                service_instance = space.get_service_instance_by_name(
                                                    service_instance_name)
                                                if service_instance:
                                                    excluded_service_instance_guids.append(
                                                        service_instance.guid)
                                    else:
                                        excluded_service_instance_guids = (excluded_service_instance_guids
                                                                           + list(space.service_instances.keys()))
        return excluded_service_instance_guids

    def dump_df_to_csv(self, data_frame, parent_folder, file_name_wo_extension):
        try:
            file = self.client.resolve_file(parent_folder, f'{file_name_wo_extension}.csv')
            data_frame.to_csv(file)
            logging.info(f'Stored the collected content into file {file}')
        except Exception as e: # pylint: disable=invalid-name
            logging.error(f'Failed to store the collected content into csv file {file}',
                          exc_info=e)
            raise

    def get_target_org_space_guids_by_name(self, org_name, **kwargs):
        kwargs.setdefault('space_name', None)
        org = self.controller.get_org_by_name(org_name)

        found_entities = []
        if bool(kwargs.get('space_name')):
            space = org.get_space_by_name(kwargs.get('space_name'))
            found_entities.append((org.guid, space.guid))
        else:
            for space_guid in org.spaces.keys():
                found_entities.append((org.guid, space_guid))
        return found_entities

    def get_target_org_space_app_guids_by_name(self, org_name, **kwargs):
        kwargs.setdefault('space_name', None)
        kwargs.setdefault('app_name', None)
        org = self.controller.get_org_by_name(org_name)
        found_entities = []
        if bool(kwargs.get('space_name')):
            space = org.get_space_by_name(kwargs.get('space_name'))
            if bool(kwargs.get('app_name')):
                app = space.get_app_by_name(kwargs.get('app_name'))
                found_entities.append((org.guid, space.guid, app.guid))
            else:
                for app_guid in space.apps.keys():
                    found_entities.append((org.guid, space.guid, app_guid))
        else:
            for space_guid in org.spaces.keys():
                space = org.get_space_by_guid(space_guid)
                for app_guid in space.apps.keys():
                    found_entities.append((org.guid, space_guid, app_guid))
        return found_entities

    # Store the information about Organization roles assigned to users in a csv file

    def store_org_roles_assignment(self):
        users = self.controller.users
        representations = []
        keys = User.get_org_representation_keys()
        for guid in users:
            orgs_representation = users[guid].orgs_representation
            if bool(orgs_representation):
                representations = representations + orgs_representation
        df_assignment = pd.DataFrame(representations, columns=keys)
        self.dump_df_to_csv(df_assignment, "users", "org_roles_assignment")

    # Store the information about Space roles assigned to users in a csv file

    def store_space_roles_assignment(self):
        users = self.controller.users
        representations = []
        keys = User.get_spaces_representation_keys()
        for guid in users:
            spaces_representation = users[guid].spaces_representation
            if bool(spaces_representation):
                representations = representations + spaces_representation
        df_assignment = pd.DataFrame(representations, columns=keys)
        self.dump_df_to_csv(df_assignment, "users", "space_roles_assignment")

    # Store the information about Role Collections roles to users in a csv file

    def store_role_collections_assignment(self):
        users = self.controller.users
        representations = []
        keys = User.get_role_collections_representation_keys()
        for guid in users:
            role_collections_representation = users[guid].role_collections_representation
            representations = representations + role_collections_representation
        df_assignment = pd.DataFrame(representations, columns=keys)
        self.dump_df_to_csv(df_assignment, "users", "role_collections_assignment")

    # Store the information about Databases known by XS Advanced in a csv file

    def store_databases(self):
        databases = self.controller.databases
        representations = []
        keys = Database.get_representation_keys()
        for guid in databases:
            representations.append(databases[guid].representation)
        df_databases = pd.DataFrame(representations, columns=keys)
        self.dump_df_to_csv(df_databases, "databases", "databases")

    # Store the information about invalid HANA service instances in a csv file

    def store_invalid_instances(self):
        databases = self.controller.databases
        representations = []
        service_instance_keys = ServiceInstance.get_representation_keys()
        keys = ['Tenant Name'] + service_instance_keys + ['Error Message']

        for database_guid in databases:
            database = databases[database_guid]
            tenant_name = database.tenant_name

            for instance_guid in database.invalid_instances:
                service_instance = database.invalid_instances[instance_guid].get(
                    'service_instance')
                error_message = database.invalid_instances[instance_guid].get(
                    'error_message')
                service_instance_representation = ((tenant_name, )
                                                   + service_instance.representation
                                                   + (error_message, ))
                representations.append(service_instance_representation)

        df_invalid_instances = pd.DataFrame(representations, columns=keys)
        self.dump_df_to_csv(df_invalid_instances,"databases", "invalid_instances")

    # Store the information about applications from a given space in a csv file

    def get_app_representations(self, org_guid, space_guid, **kwargs):
        kwargs.setdefault('restricted_app_guids', None)
        kwargs.setdefault('restricted_instance_guids', None)
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        representations = []

        for app_guid in space.apps:
            if (app_guid in list(kwargs.get('restricted_app_guids') or [])
                or kwargs.get('restricted_app_guids') is None):

                app = space.get_app_by_guid(app_guid)
                app_representation = app.representation
                if len(app.instances) == 0:
                    instance_representation = ApplicationInstance.get_blank_representation()
                    representations.append(
                        app_representation + instance_representation)

                else:
                    for instance_guid in app.instances:
                        if (instance_guid in list(kwargs.get('restricted_instance_guids') or [])
                            or kwargs.get('restricted_instance_guids') is None):

                            instance = app.instances[instance_guid]
                            instance_representation = instance.representation
                            representations.append(
                                app_representation + instance_representation)
        return representations

    def store_applications(self, org_guid, space_guid, **kwargs):
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        representations = self.get_app_representations(org_guid, space_guid, **kwargs)
        keys = (Application.get_representation_keys()
                + ApplicationInstance.get_representation_keys())
        df_apps = pd.DataFrame(representations, columns=keys)
        self.dump_df_to_csv(df_apps, f"apps/{org.name}/{space.name}", "apps")

    # Store the information about service instances from a given space in a csv file

    def get_service_instance_representations(self, org_guid, space_guid, **kwargs):
        kwargs.setdefault('restricted_instance_guids', None)
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        representations = []
        for guid in space.service_instances:
            if (guid in list(kwargs.get('restricted_instance_guids') or [])
                or kwargs.get('restricted_instance_guids') is None):

                service_instance = space.get_service_instance_by_guid(guid)
                representations.append((service_instance.representation
                                        + service_instance.app_relations_representation))
        return representations

    def store_service_instances(self, org_guid, space_guid, **kwargs):
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        representations = self.get_service_instance_representations(org_guid, space_guid, **kwargs)
        keys = ServiceInstance.get_representation_keys() + ServiceInstance.get_app_relations_keys()
        df_service_instances = pd.DataFrame(representations, columns=keys)
        self.dump_df_to_csv(
            df_service_instances, f"services/{org.name}/{space.name}", "service_instances")
    
    # Store the information about user-provided service instances from a given space in a csv file

    def get_ups_service_instance_representations(self, org_guid, space_guid, **kwargs):
        kwargs.setdefault('restricted_instance_guids', None)
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        representations = []
        for guid in space.ups_service_instances:
            if (guid in list(kwargs.get('restricted_instance_guids') or [])
                or kwargs.get('restricted_instance_guids') is None):
                ups_service_instance = space.get_ups_service_instance_by_guid(guid)
                representations.append(ups_service_instance.representation)
        return representations

    def store_ups_service_instances(self, org_guid, space_guid, **kwargs):
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        representations = self.get_ups_service_instance_representations(org_guid, space_guid, **kwargs)
        keys = UserProvidedServiceInstance.get_representation_keys()
        df_service_instances = pd.DataFrame(representations, columns=keys)
        self.dump_df_to_csv(
            df_service_instances, f"services/{org.name}/{space.name}", "user_provided_service_instances")

    # Store the information about service keys from a given space in a csv file

    def get_service_key_representations(self, org_guid, space_guid):
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        representations = []
        for instance_guid in space.service_instances:
            service_instance = space.get_service_instance_by_guid(instance_guid)
            service_representation = service_instance.representation
            if len(service_instance.service_keys) != 0:
                for key_guid in service_instance.service_keys:
                    service_key = service_instance.service_keys[key_guid]
                    service_key_representation = service_key.representation
                    representations.append((service_representation
                                            + service_key_representation))
        return representations

    def store_service_instance_keys(self, org_guid, space_guid):
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        representations = self.get_service_key_representations(org_guid, space_guid)
        keys = (ServiceInstance.get_representation_keys()
                + ServiceKey.get_representation_keys())

        df_service_instances = pd.DataFrame(representations, columns=keys)
        self.dump_df_to_csv(
            df_service_instances, f"services/{org.name}/{space.name}", "service_instance_keys")

    # Operate with continously crashing apps

    def get_continuously_crashing_app_guids(self, org_guid, space_guid):
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)
        found_guids = []
        for guid in space.apps:
            if not space.apps[guid].state == 'STOPPED':
                crashed_short_term_count = space.apps[guid].crashed_short_term_count
                crashed_mid_term_count = space.apps[guid].crashed_mid_term_count
                # Assumed 3 crashes is a short term as a critical threshold
                # Assumed 1 crash in a short term and 10 crashes in a midterm
                # as a critical threshold
                if crashed_short_term_count >= 1:
                    if crashed_mid_term_count >= 10:
                        found_guids.append(guid)
                    else:
                        if crashed_short_term_count >= 3:
                            found_guids.append(guid)
        return found_guids

    def store_continuously_crashing_apps(self, org_guid, space_guid):
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        found_guids = self.get_continuously_crashing_app_guids(org_guid, space_guid)
        if found_guids:
            representations = self.get_app_representations(org_guid,
                                                           space_guid,
                                                           restricted_app_guids=found_guids)
            keys = Application.get_representation_keys(
            ) + ApplicationInstance.get_representation_keys()
            df_apps = pd.DataFrame(representations, columns=keys)
            self.dump_df_to_csv(
                df_apps, f'apps/{org.name}/{space.name}', 'continously_crashing_apps')

    # Operate with app and service instances

    def get_app_instance_guids_by_state(self, org_guid, space_guid, **kwargs):
        kwargs.setdefault('target_states', None)

        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        found_instances = []

        for app_guid in space.apps:
            app = space.get_app_by_guid(app_guid)
            if not len(app.instances) == 0:
                for instance_guid in app.instances:
                    instance = app.instances[instance_guid]
                    if (instance.state in kwargs.get('target_states')
                        or kwargs.get('target_states') is None):
                        found_instances.append((app_guid, instance_guid))
        return found_instances

    def get_app_guids_by_filter(self, org_guid, space_guid, **kwargs):
        kwargs.setdefault('belongs_to_mta', None)
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)
        found_guids = []
        for guid in space.apps:
            app = space.get_app_by_guid(guid)
            if (app.belongs_to_mta == kwargs.get('belongs_to_mta')
                or kwargs.get('belongs_to_mta') is None):
                found_guids.append(guid)
        return found_guids

    def get_service_instance_guids_by_filter(self, org_guid, space_guid, **kwargs):
        kwargs.setdefault('has_non_di_mta_bindings', None)
        kwargs.setdefault('has_non_di_mta_references', None)

        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        found_guids = []
        for guid in space.service_instances:
            service_instance = space.get_service_instance_by_guid(guid)

            app_has_non_di_mta_bindings = bool(
                service_instance.app_relations.get('count_non_di_mta_bindings'))
            app_has_non_di_mta_references = bool(
                service_instance.app_relations.get('count_non_di_mta_references'))

            match_binding_requirements = (app_has_non_di_mta_bindings == kwargs.get('has_non_di_mta_bindings')
                                          or kwargs.get('has_non_di_mta_bindings') is None)
            match_reference_requirements = (app_has_non_di_mta_references == kwargs.get('has_non_di_mta_references')
                                            or kwargs.get('has_non_di_mta_references') is None)
            match_requirements = match_binding_requirements and match_reference_requirements
            if match_requirements:
                found_guids.append(guid)
        return found_guids

    def get_non_mta_app_service_instance_guids(self, org_guid, space_guid):
        found_app_guids = self.get_app_guids_by_filter(org_guid,
                                                       space_guid,
                                                       belongs_to_mta=False)
        found_service_instance_guids = self.get_service_instance_guids_by_filter(
            org_guid, space_guid, has_non_di_mta_bindings=False, has_non_di_mta_references=False)
        return found_app_guids, found_service_instance_guids

    def store_non_mta_apps_service_instances(self, org_guid, space_guid):
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)

        found_app_guids, found_service_instance_guids = self.get_non_mta_app_service_instance_guids(org_guid,
                                                                                                    space_guid)

        app_representations = self.get_app_representations(org_guid,
                                                           space_guid,
                                                           restricted_app_guids=found_app_guids)

        app_keys = (Application.get_representation_keys()
                    + ApplicationInstance.get_representation_keys())

        df_apps = pd.DataFrame(app_representations, columns=app_keys)

        service_instance_representations = self.get_service_instance_representations(
            org_guid, space_guid, restricted_instance_guids=found_service_instance_guids)

        serv_keys = (ServiceInstance.get_representation_keys()
                     + ServiceInstance.get_app_relations_keys())

        df_service_instances = pd.DataFrame(service_instance_representations, columns=serv_keys)

        self.dump_df_to_csv(df_apps,
                            f"apps/{org.name}/{space.name}",
                            "non_mta_apps")
        self.dump_df_to_csv(df_service_instances,
                            f"services/{org.name}/{space.name}",
                            "non_mta_service_instances")

    def store_app_router_log(self, org_guid, space_guid, app_guid):
        org = self.controller.get_org_by_guid(org_guid)
        space = org.get_space_by_guid(space_guid)
        app = space.get_app_by_guid(app_guid)
        app_router_log_representation = app.logs.router_log_representation
        app_router_log_keys = ApplicationLogs.get_router_log_representation_keys()
        df_app_router_log = pd.DataFrame(app_router_log_representation,
                                         columns=app_router_log_keys)
        self.dump_df_to_csv(df_app_router_log,
                            f"apps/{org.name}/{space.name}/{app.name}",
                            "router_log")
