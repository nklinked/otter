import logging
import functools


class Cleaner:

    def __init__(self, controller, collector, client):
        self.controller = controller
        self.collector = collector
        self.client = client

    def check_experimental_features(operation):
        @functools.wraps(operation)
        def run_operation(*args, **kwargs):
            enabled = args[0].client.get_experimental_features_status()
            try:
                if not enabled:
                    raise Exception(
                        'Experimental features are not enabled and the operation is not permitted')
            except Exception as e: # pylint: disable=invalid-name
                logging.error(('Experimental features are not enabled '
                               'and the operation is not permitted'), exc_info=e)
                raise
            else:
                return operation(*args, **kwargs)
        return run_operation

    @check_experimental_features
    def stop_continuously_crashing_apps(self, org_guid, space_guid, **kwargs):
        excluded_app_guids = self.collector.get_excluded_app_guids(**kwargs)
        stopped = False

        required_app_instance_guids = self.collector.get_continuously_crashing_app_guids(org_guid,
                                                                                         space_guid)
        target_app_guids = [
            guid for guid in required_app_instance_guids if guid not in excluded_app_guids]

        if target_app_guids:
            for app_guid in target_app_guids:
                stopped = self.controller.stop_app(app_guid)
                if stopped:
                    logging.info(f'Stopped application {app_guid}')
                else:
                    logging.info(f'Failed to stop application {app_guid}')
            logging.info('Stopped all application matching the given criteria')
        else:
            logging.info(
                'No continously crashing applications are identified matching the given criteria')

    @check_experimental_features
    def delete_app_instances_by_state(self, org_guid, space_guid, **kwargs):
        excluded_app_guids = self.collector.get_excluded_app_guids(**kwargs)
        deleted = False

        required_app_instance_guids = self.collector.get_app_instance_guids_by_state(org_guid,
                                                                                     space_guid,
                                                                                     **kwargs)
        target_app_instance_guids = [app_instance_guids for app_instance_guids in required_app_instance_guids # pylint: disable=line-too-long
                                     if app_instance_guids[0] not in excluded_app_guids]

        if target_app_instance_guids:
            for app_instance_guids in target_app_instance_guids:
                app_guid, instance_guid = app_instance_guids
                deleted = self.controller.delete_app_instance(app_guid, instance_guid)
                if deleted:
                    logging.info(f'Deleted instance {instance_guid} of application {app_guid}')
                else:
                    logging.info(
                        f'Failed to delete instance {instance_guid} of application {app_guid}')
            logging.info('Deleted all application instances matching the given criteria')
        else:
            logging.info(
                'No application instances are identified for deletion matching the given criteria')

    @check_experimental_features
    def delete_non_mta_app_service_instances(self, org_guid, space_guid, **kwargs):
        excluded_app_guids = self.collector.get_excluded_app_guids(**kwargs)
        excluded_service_instance_guids = self.collector.get_excluded_service_instance_guids(**kwargs) # pylint: disable=line-too-long

        required_app_guids, required_service_instance_guids = self.collector.get_non_mta_app_service_instance_guids(org_guid, # pylint: disable=line-too-long
                                                                                                                    space_guid) # pylint: disable=line-too-long

        target_app_guids = [guid for guid in required_app_guids if guid not in excluded_app_guids]
        target_service_instance_guids = [guid for guid in required_service_instance_guids
                                         if guid not in excluded_service_instance_guids]

        if target_app_guids:
            for app_guid in target_app_guids:
                deleted = self.controller.delete_app_gracefully(org_guid, space_guid, app_guid)
                if deleted:
                    logging.info(f'Gracefully deleted application {app_guid}')
                else:
                    logging.info(f'Failed to gracefully delete application {app_guid}')
            logging.info('Deleted all possible applications matching the given criteria')
        else:
            logging.info('No applications are identified for deletion matching the given criteria')

        # Sequential deletion
        if target_service_instance_guids:
            for service_instance_guid in target_service_instance_guids:
                deleted = self.controller.delete_service_instance(service_instance_guid)
                if deleted:
                    logging.info(f'Deleted service instance {service_instance_guid}')
                else:
                    logging.info(f'Failed to delete service instance {service_instance_guid}')
            logging.info('Deleted all possible applications matching the given criteria')
        else:
            logging.info(
                'No service instances are identified for deletion matching the given criteria')

        # Parallel deletion
        # self.controller.delete_service_instances(target_service_instance_guids)
