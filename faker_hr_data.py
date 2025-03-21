import csv
import random
import time
from faker import Faker

# Initialize Faker
faker = Faker()

# Predefined lists for synthetic data
job_titles = [
    "Data Analyst", "HR Specialist", "Public Policy Advisor", "IT Manager", 
    "Project Coordinator", "Administrative Assistant", "Systems Analyst", 
    "Program Manager", "Budget Analyst", "Operations Manager"
]

agency_levels = ["Local", "State", "Municipal", "Federal"]

# Common skills for government HR / tech roles
skills_list = [
    "Python", "SQL", "Data Analysis", "Public Policy", "Communication", 
    "Project Management", "Cloud Computing", "AI", "Leadership", "Budgeting", 
    "Microsoft Office", "Negotiation", "Strategic Planning", "Customer Service"
]

classification_levels = ["GS-5", "GS-7", "GS-9", "GS-11", "GS-13", "Band I", "Band II", "Band III"]

work_types = ["Remote", "Hybrid", "On-site"]

# Function to generate a synthetic HR job row
def generate_job_row(job_id):
    row = {}
    row["job_id"] = job_id
    row["job_title"] = random.choice(job_titles)
    row["agency_level"] = random.choice(agency_levels)
    
    # Generate agency name based on agency level
    if row["agency_level"] == "Municipal":
        row["agency_name"] = f"City of {faker.city()}"
    elif row["agency_level"] == "Local":
        row["agency_name"] = f"County of {faker.city()}"
    elif row["agency_level"] == "State":
        row["agency_name"] = f"{faker.state()} Department of {random.choice(['Health', 'Education', 'Transportation', 'Public Safety'])}"
    else:  # Federal
        row["agency_name"] = f"U.S. {random.choice(['Department of Justice', 'Department of Education', 'Department of Health and Human Services', 'Department of Transportation'])}"
    
    # Location: City, ST
    row["location"] = f"{faker.city()}, {faker.state_abbr()}"
    
    # Job description text
    row["description"] = faker.paragraph(nb_sentences=5)
    
    # Salary ranges
    min_salary = random.randint(40000, 80000)
    max_salary = random.randint(min_salary, min_salary + 30000)
    row["min_salary"] = min_salary
    row["max_salary"] = max_salary
    
    # Required skills: randomly select 3-6 skills from the list
    row["required_skills"] = ", ".join(random.sample(skills_list, random.randint(3, 6)))
    
    # Classification level
    row["classification_level"] = random.choice(classification_levels)
    
    # Posted date within the past 2 years
    row["posted_date"] = faker.date_between(start_date="-2y", end_date="today").strftime("%Y-%m-%d")
    
    # Hiring timeline: random days between 30 and 120
    row["hiring_timeline_days"] = random.randint(30, 120)
    
    # Work type
    row["work_type"] = random.choice(work_types)
    
    return row

def main():
    output_csv = "synthetic_hr_jobs.csv"
    csv_columns = [
        "job_id", "job_title", "agency_level", "agency_name", "location",
        "description", "min_salary", "max_salary", "required_skills",
        "classification_level", "posted_date", "hiring_timeline_days", "work_type"
    ]
    
    # Set the total number of rows for the dataset (e.g., 500,000)
    total_rows = 500_000  # Change this value as needed
    
    start_time = time.time()
    
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        
        for i in range(1, total_rows + 1):
            row = generate_job_row(i)
            writer.writerow(row)
            if i % 10000 == 0:
                print(f"Generated {i} rows so far...")
    
    end_time = time.time()
    print(f"Dataset generation completed in {round(end_time - start_time, 2)} seconds")

if __name__ == "__main__":
    main()
