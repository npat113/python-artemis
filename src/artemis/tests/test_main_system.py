from dataclasses import dataclass
import threading
import pytest
from typing import Any, Callable
from flask.testing import FlaskClient
from src.artemis.parameters import FullParameters

from src.artemis.main import create_app, Status, Actions
from src.artemis.devices.det_dim_constants import EIGER_TYPE_EIGER2_X_4M
import json
from time import sleep


FGS_ENDPOINT = "/fast_grid_scan/"
START_ENDPOINT = FGS_ENDPOINT + Actions.START.value
STOP_ENDPOINT = FGS_ENDPOINT + Actions.STOP.value
STATUS_ENDPOINT = FGS_ENDPOINT + "status"
SHUTDOWN_ENDPOINT = FGS_ENDPOINT + Actions.SHUTDOWN.value
TEST_PARAMS = FullParameters().to_json()


class MockRunEngine:
    RE_takes_time = True
    aborting_takes_time = False
    error: str = None

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        while self.RE_takes_time:
            sleep(0.1)
            if self.error:
                raise Exception(self.error)

    def abort(self):
        while self.aborting_takes_time:
            sleep(0.1)
            if self.error:
                raise Exception(self.error)
        self.RE_takes_time = False


@dataclass
class ClientAndRunEngine:
    client: FlaskClient
    mock_run_engine: MockRunEngine


@pytest.fixture
def test_env():
    mock_run_engine = MockRunEngine()
    app, runner = create_app({"TESTING": True}, mock_run_engine)
    runner_thread = threading.Thread(target=runner.wait_on_queue)
    runner_thread.start()
    with app.test_client() as client:
        yield ClientAndRunEngine(client, mock_run_engine)

    runner.shutdown()
    runner_thread.join()


def wait_for_run_engine_status(
    client: FlaskClient,
    status_check: Callable[[str], bool] = lambda status: status != Status.BUSY.value,
    attempts=10,
):
    while attempts != 0:
        response = client.get(STATUS_ENDPOINT)
        response_json = json.loads(response.data)
        if status_check(response_json["status"]):
            return response_json
        else:
            attempts -= 1
            sleep(0.1)
    assert False, "Run engine still busy"


def check_status_in_response(response_object, expected_result: Status):
    response_json = json.loads(response_object.data)
    assert response_json["status"] == expected_result.value


def test_start_gives_success(test_env: ClientAndRunEngine):
    response = test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    check_status_in_response(response, Status.SUCCESS)


def test_getting_status_return_idle(test_env: ClientAndRunEngine):
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.IDLE)


def test_getting_status_after_start_sent_returns_busy(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.BUSY)


def test_sending_start_twice_fails(test_env: ClientAndRunEngine):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    response = test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    check_status_in_response(response, Status.FAILED)


def test_given_started_when_stopped_then_success_and_idle_status(
    test_env: ClientAndRunEngine,
):
    test_env.mock_run_engine.aborting_takes_time = True
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    response = test_env.client.put(STOP_ENDPOINT)
    check_status_in_response(response, Status.ABORTING)
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.ABORTING)
    test_env.mock_run_engine.aborting_takes_time = False
    wait_for_run_engine_status(
        test_env.client, lambda status: status != Status.ABORTING
    )
    check_status_in_response(response, Status.ABORTING)


def test_given_started_when_stopped_and_started_again_then_runs(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.client.put(STOP_ENDPOINT)
    response = test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    check_status_in_response(response, Status.SUCCESS)
    response = test_env.client.get(STATUS_ENDPOINT)
    check_status_in_response(response, Status.BUSY)


def test_given_started_when_RE_stops_on_its_own_with_error_then_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    error_message = "D'Oh"
    test_env.mock_run_engine.error = error_message
    response_json = wait_for_run_engine_status(test_env.client)
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == error_message


def test_given_started_and_return_status_interrupted_when_RE_aborted_then_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.mock_run_engine.aborting_takes_time = True
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    error_message = "D'Oh"
    test_env.client.put(STOP_ENDPOINT)
    test_env.mock_run_engine.error = error_message
    response_json = wait_for_run_engine_status(
        test_env.client, lambda status: status != Status.ABORTING.value
    )
    assert response_json["status"] == Status.FAILED.value
    assert response_json["message"] == error_message


def test_given_started_when_RE_stops_on_its_own_happily_then_no_error_reported(
    test_env: ClientAndRunEngine,
):
    test_env.client.put(START_ENDPOINT, data=TEST_PARAMS)
    test_env.mock_run_engine.RE_takes_time = False
    response_json = wait_for_run_engine_status(test_env.client)
    assert response_json["status"] == Status.IDLE.value
