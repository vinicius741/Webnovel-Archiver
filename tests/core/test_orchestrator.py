import os
import shutil
import unittest
from unittest.mock import MagicMock, patch, call, mock_open
import datetime
import copy # For deepcopying progress data
import json

from webnovel_archiver.core.orchestrator import archive_story
from webnovel_archiver.core.fetchers.base_fetcher import StoryMetadata, ChapterInfo

if __name__ == '__main__':
    unittest.main()