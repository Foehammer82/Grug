import logging
from unittest.mock import Mock, patch

from grug.log_config import InterceptHandler, init_logging


def test_initialize_metrics():
    init_logging()

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.warning("Test log message")


@patch("grug.log_config.logger")
def test_emit(mock_logger):
    # Arrange
    handler = InterceptHandler()
    mock_record = Mock(spec=logging.LogRecord)
    mock_record.levelname = "INFO"
    mock_record.getMessage.return_value = "Test message"
    mock_record.exc_info = None

    # Act
    handler.emit(mock_record)

    # Assert
    mock_logger.opt.assert_called_once()
