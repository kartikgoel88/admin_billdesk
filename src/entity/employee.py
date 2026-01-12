from dataclasses import dataclass


@dataclass
class Employee:
    def __init__(self,id,name,emp_month,client):
        self.emp_id = id
        self.emp_name = name
        self.emp_month = emp_month
        self.client = client

    def to_dict(self) -> dict:
        return {
            "emp_id": self.emp_id,
            "emp_name": self.emp_name,
            "emp_month": self.emp_month,
            "client": self.client
        }