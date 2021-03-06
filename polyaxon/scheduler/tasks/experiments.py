import logging

import publisher

from constants.experiments import ExperimentLifeCycle
from db.getters.experiments import get_valid_experiment
from db.models.experiments import ExperimentMetric
from libs.paths.experiments import copy_experiment_outputs
from polyaxon.celery_api import app as celery_app
from polyaxon.settings import SchedulerCeleryTasks
from scheduler import dockerizer_scheduler, experiment_scheduler
from schemas.specifications import ExperimentSpecification

_logger = logging.getLogger('polyaxon.scheduler.experiments')


def copy_experiment(experiment):
    """If experiment is a restart, we should resume from last check point"""
    try:
        publisher.publish_experiment_job_log(
            log_lines='Copying outputs from experiment `{}` into experiment `{}`'.format(
                experiment.original_experiment.unique_name, experiment.unique_name
            ),
            status=ExperimentLifeCycle.BUILDING,
            experiment_uuid=experiment.uuid.hex,
            experiment_name=experiment.unique_name,
            job_uuid='all',
        )
        copy_experiment_outputs(
            persistence_outputs_from=experiment.original_experiment.persistence_outputs,
            persistence_outputs_to=experiment.persistence_outputs,
            experiment_name_from=experiment.original_experiment.unique_name,
            experiment_name_to=experiment.unique_name)

    except OSError:
        publisher.publish_experiment_job_log(
            log_lines='Could not copy the outputs of experiment `{}` into experiment `{}`'.format(
                experiment.original_experiment.unique_name, experiment.unique_name
            ),
            status=ExperimentLifeCycle.BUILDING,
            experiment_uuid=experiment.uuid.hex,
            experiment_name=experiment.unique_name,
            job_uuid='all',
        )
        _logger.warning(
            'Could not copy the outputs of experiment `%s` into experiment `%s`',
            experiment.original_experiment.unique_name, experiment.unique_name)


@celery_app.task(name=SchedulerCeleryTasks.EXPERIMENTS_BUILD, ignore_result=True)
def experiments_build(experiment_id):
    experiment = get_valid_experiment(experiment_id=experiment_id)
    if not experiment:
        return

    # No need to build the image, start the experiment directly
    if not (experiment.specification.build and experiment.specification.run):
        celery_app.send_task(
            SchedulerCeleryTasks.EXPERIMENTS_START,
            kwargs={'experiment_id': experiment_id})
        return

    if not ExperimentLifeCycle.can_transition(status_from=experiment.last_status,
                                              status_to=ExperimentLifeCycle.BUILDING):
        _logger.info('Experiment id `%s` cannot transition from `%s` to `%s`.',
                     experiment_id, experiment.last_status, ExperimentLifeCycle.BUILDING)
        return

    build_job, image_exists, build_status = dockerizer_scheduler.create_build_job(
        user=experiment.user,
        project=experiment.project,
        config=experiment.specification.build,
        code_reference=experiment.code_reference)

    experiment.build_job = build_job
    experiment.save()
    if image_exists:
        # The image already exists, so we can start the experiment right away
        celery_app.send_task(
            SchedulerCeleryTasks.EXPERIMENTS_START,
            kwargs={'experiment_id': experiment_id})
        return

    if not build_status:
        experiment.set_status(ExperimentLifeCycle.FAILED, message='Could not start build process.')
        return

    # Update experiment status to show that its building
    experiment.set_status(ExperimentLifeCycle.BUILDING)


@celery_app.task(name=SchedulerCeleryTasks.EXPERIMENTS_CHECK_STATUS, ignore_result=True)
def experiments_check_status(experiment_uuid=None, experiment_id=None):
    experiment = get_valid_experiment(experiment_id=experiment_id, experiment_uuid=experiment_uuid)
    if not experiment:
        return
    experiment.update_status()


@celery_app.task(name=SchedulerCeleryTasks.EXPERIMENTS_SET_METRICS, ignore_result=True)
def experiments_set_metrics(experiment_uuid, metrics, created_at=None):
    experiment = get_valid_experiment(experiment_uuid=experiment_uuid)
    if not experiment:
        return

    kwargs = {}
    if created_at:
        kwargs['created_at'] = created_at
    ExperimentMetric.objects.create(experiment=experiment, values=metrics, **kwargs)


@celery_app.task(name=SchedulerCeleryTasks.EXPERIMENTS_START, ignore_result=True)
def experiments_start(experiment_id):
    experiment = get_valid_experiment(experiment_id=experiment_id)
    if not experiment:
        _logger.info('Something went wrong, '
                     'the Experiment `%s` does not exist anymore.', experiment_id)
        return

    if not ExperimentLifeCycle.can_transition(status_from=experiment.last_status,
                                              status_to=ExperimentLifeCycle.SCHEDULED):
        _logger.info('Experiment `%s` cannot transition from `%s` to `%s`.',
                     experiment.unique_name, experiment.last_status, ExperimentLifeCycle.SCHEDULED)
        return None

    experiment_scheduler.start_experiment(experiment)


@celery_app.task(name=SchedulerCeleryTasks.EXPERIMENTS_STOP, ignore_result=True)
def experiments_stop(project_name,
                     project_uuid,
                     experiment_name,
                     experiment_group_name,
                     experiment_group_uuid,
                     experiment_uuid,
                     specification,
                     update_status=True):
    specification = ExperimentSpecification.read(specification)
    experiment_scheduler.stop_experiment(
        project_name=project_name,
        project_uuid=project_uuid,
        experiment_name=experiment_name,
        experiment_group_name=experiment_group_name,
        experiment_group_uuid=experiment_group_uuid,
        experiment_uuid=experiment_uuid,
        specification=specification,
    )

    if not update_status:
        return

    experiment = get_valid_experiment(experiment_uuid=experiment_uuid)
    if not experiment:
        _logger.info('Something went wrong, '
                     'the Experiment `%s` does not exist anymore.', experiment_uuid)
        return

    # Update experiment status to show that its stopped
    experiment.set_status(ExperimentLifeCycle.STOPPED,
                          message='Experiment was stopped')
