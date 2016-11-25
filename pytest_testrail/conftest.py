import configparser

from .plugin import TestRailPlugin
from .testrail_api import APIClient
from .plugin import get_tests_list


def pytest_addoption(parser):
    group = parser.getgroup('testrail')
    group.addoption(
        '--testrail',
        action='store',
        help='Create and update testruns with TestRail')
    group.addoption(
        '--no-ssl-cert-check',
        action='store_true',
        default=False,
        required=False,
        help='Do not check for valid SSL certificate on TestRail host'
    )
    group.addoption(
        '--tr_name',
        action='store',
        default=None,
        required=False,
        help='Name given to testrun, that appears in TestRail'
    )
    group.addoption(
        '--run_id',
        action='store',
        required=False,
        help='Name gives run_id for running'
    )
    group.addoption(
        '--milestone_id',
        action='store',
        required=False,
        help='Name gives milestone_id for creating new run'
    )


def pytest_configure(config):
    if config.option.testrail:
        cfg_file = read_config_file(config.getoption("--testrail"))
        client = APIClient(cfg_file.get('API', 'url'))
        client.user = cfg_file.get('API', 'email')
        client.password = cfg_file.get('API', 'password')
        ssl_cert_check = True
        tr_name = config.getoption('--tr_name')
        run_id = config.getoption('--run_id')
        milestone_id = config.getoption('--milestone_id')
        if run_id:
            get_tests_list(client=client, run_id=run_id, cert=ssl_cert_check)

        elif config.getoption('--no-ssl-cert-check') is True:
            ssl_cert_check = False

        config.pluginmanager.register(
            TestRailPlugin(
                client=client,
                assign_user_id=cfg_file.get('TESTRUN', 'assignedto_id'),
                project_id=cfg_file.get('TESTRUN', 'project_id'),
                suite_id=cfg_file.get('TESTRUN', 'suite_id'),
                type_id=cfg_file.get('TESTRUN', 'type_id'),
                cert_check=ssl_cert_check,
                tr_name=tr_name,
                run_id=run_id,
                milestone_id=milestone_id
            )
        )


def read_config_file(configfile):
    config = configparser.ConfigParser()
    config.read(configfile)
    return config

