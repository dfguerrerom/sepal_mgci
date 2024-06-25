from pathlib import Path
import io
import logging
import json
import component.parameter.directory as DIR

from sepal_ui.scripts.warning import SepalWarning


import ee
import numpy as np
from apiclient import discovery
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials

logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

__all__ = ["GDrive"]


class GDrive:
    def __init__(self):
        home_path = Path.home()
        credentials_file = (
            ".config/earthengine/credentials"
            if "sepal-user" in home_path.name
            else ".config/earthengine/sepal_credentials"
        )
        credentials_path = home_path / credentials_file

        self.access_token = json.loads((credentials_path).read_text()).get(
            "access_token"
        )
        self.service = discovery.build(
            serviceName="drive",
            version="v3",
            cache_discovery=False,
            credentials=Credentials(self.access_token),
        )

    def print_file_list(self):
        service = self.service

        results = (
            service.files()
            .list(pageSize=30, fields="nextPageToken, files(id, name)")
            .execute()
        )
        items = results.get("files", [])
        if not items:
            print("No files found.")
        else:
            print("Files:")
            for item in items:
                print("{0} ({1})".format(item["name"], item["id"]))

    def get_items(self):
        service = self.service

        # get list of files
        results = (
            service.files()
            .list(
                q="mimeType='text/csv'",
                pageSize=1000,
                fields="nextPageToken, files(id, name)",
            )
            .execute()
        )
        items = results.get("files", [])

        return items

    def get_id(self, filename):

        items = self.get_items()
        # extract list of names and id and find the wanted file
        namelist = np.array([items[i]["name"] for i in range(len(items))])
        idlist = np.array([items[i]["id"] for i in range(len(items))])
        file_pos = np.where(namelist == filename)

        if len(file_pos[0]) == 0:
            return (0, filename + " not found")
        else:
            return (1, idlist[file_pos])

    def download_file(self, filename, output_file):

        # get file id
        success, fId = self.get_id(filename)
        if success == 0:
            print(filename + " not found")
            return

        request = self.service.files().get_media(fileId=fId[0])
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            # print('Download %d%%.' % int(status.progress() * 100))

        fo = open(output_file, "wb")
        fo.write(fh.getvalue())
        fo.close()

    def delete_file(self, items_to_search, filename):

        # get file id
        success, fId = self.get_id(items_to_search, filename)

        if success == 0:
            print(filename + " not found")

        self.service.files().delete(fileId=fId[0]).execute()

    def get_task(self, task_id):
        """Get the current state of the task"""

        tasks_list = ee.batch.Task.list()
        for task in tasks_list:
            if task.id == task_id:
                return task

        raise Exception(f"The task id {task_id} doesn't exist in your tasks.")

    def download_from_task_file(self, task_id, tasks_file, task_filename):
        """Download csv file result from GDrive

        Args:
            task_id (str): id of the task tasked in GEE.
            tasks_file (Path): path file containing all task_id, task_name
            task_filename (str): name of the task file to be downloaded.
        """

        # Check if the task is completed
        task = self.get_task(task_id.strip())

        if task.state == "COMPLETED":
            tmp_result_folder = Path(DIR.TASKS_DIR, Path(tasks_file.name).stem)
            tmp_result_folder.mkdir(exist_ok=True)

            tmp_result_file = tmp_result_folder / task_filename
            self.download_file(task_filename, tmp_result_file)

            return tmp_result_file

        elif task.state == "FAILED":
            raise Exception(f"The task {Path(task_filename).stem} failed.")

        else:
            raise SepalWarning(
                f"The task '{Path(task_filename).stem}' state is: {task.state}."
            )
