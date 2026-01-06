from dataclasses import dataclass


@dataclass
class Employee:
    def __init__(self,id,name,month,client):
        self.emp_id = id
        self.emp_name = name
        self.month = month
        self.client = client

    def to_dict(self) -> dict:
        return {
            "emp_id": self.emp_id,
            "emp_name": self.emp_name,
            "month": self.month,
            "client": self.client
        }