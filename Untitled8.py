#!/usr/bin/env python
# coding: utf-8

# In[33]:


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
import time
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# Path to your ChromeDriver executable
chrome_driver_path = './chromedriver'  # Change this to the actual path of chromedriver

# Set up the Service object with the executable path

# Set up Chrome options (optional, for headless mode, etc.)
options = Options()
options.add_argument('--headless')  # Uncomment if you want to run it in headless mode
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

options.binary_location = "/usr/bin/chromium-browser"

# Set up the WebDriver with the Service and options
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 10)  # Initialize WebDriverWait here

# CMS Login URL
cms_url = "https://cms.bahria.edu.pk/Logins/Student/Login.aspx"
lms_url = "https://lms.bahria.edu.pk/Student/Assignments.php"

# Step 1: Login to CMS
def login_to_cms(username, password):
    driver.get(cms_url)
    time.sleep(2)
    
    # Wait for the enrollment field to be visible before interacting with it
    enrollment_field = wait.until(EC.visibility_of_element_located((By.ID, "BodyPH_tbEnrollment")))
    enrollment_field.send_keys(username)

    # Wait for the password field to be visible
    password_field = wait.until(EC.visibility_of_element_located((By.ID, "BodyPH_tbPassword")))
    password_field.send_keys(password)

    # For Campus selection
    institute_dropdown = wait.until(EC.visibility_of_element_located((By.ID, "BodyPH_ddlInstituteID")))
    select_institute = Select(institute_dropdown)
    select_institute.select_by_visible_text("Karachi Campus")

    # For Role selection (if not default)
    role_dropdown = wait.until(EC.visibility_of_element_located((By.ID, "BodyPH_ddlSubUserType")))
    select_role = Select(role_dropdown)
    select_role.select_by_visible_text("Student")

    driver.find_element(By.ID, "BodyPH_btnLogin").send_keys(Keys.RETURN)
    time.sleep(5)  # Wait for the login to complete
    
# Step 2: Navigate to LMS and open Assignments
def navigate_to_lms():
    driver.get("https://cms.bahria.edu.pk/Sys/Common/GoToLMS.aspx")
    time.sleep(3)  # Wait for LMS to load

# Step 3: Extract assignments for a given course
def extract_assignments():
    assignments_data = []

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    assignments_table = soup.find("table")
    
    if not assignments_table:
        print("No assignments found for this course.")
        return []

    rows = assignments_table.find_all("tr")[1:]

    for row in rows:
        cells = row.find_all("td")
        if len(cells) > 6:  # Ensure there are enough columns
            assignment_name = cells[1].text.strip()
            deadline = cells[7].text.strip()
            if cells[6].text.strip() == "Deadline Exceeded":
                continue
            assignments_data.append({"Assignment": assignment_name, "Deadline": deadline})

    return assignments_data

# Step 4: Extract assignments for all courses
def extract_all_courses():
    driver.get(lms_url)
    time.sleep(2)

    all_assignments = []

    # Refresh the dropdown options each time to avoid stale references
    while True:
        try:
            course_dropdown = wait.until(EC.presence_of_element_located((By.NAME, "courseName")))
            select = Select(course_dropdown)
            options = [option.text.strip() for option in select.options if option.text.strip() and option.text.strip() != "Select Course"]
            break  # Break the loop if the dropdown is successfully located
        except StaleElementReferenceException:
            continue  # Retry if the element went stale

    # Iterate through all courses
    for course_name in options:
        print(f"Fetching assignments for: {course_name}")

        # Refresh dropdown each time to prevent stale element issues
        course_dropdown = wait.until(EC.presence_of_element_located((By.NAME, "courseName")))
        select = Select(course_dropdown)
        
        try:
            select.select_by_visible_text(course_name)
            time.sleep(0.5)  # Give it some time to load the assignments page

            # Extract assignments
            assignments = extract_assignments()
            for assignment in assignments:
                assignment["Course"] = course_name
                all_assignments.append(assignment)

        except StaleElementReferenceException:
            print(f"Stale element encountered. Retrying for course: {course_name}")
            continue  # Retry with the next course if the dropdown goes stale

    return all_assignments

# Step 5: Save assignments to a CSV
def save_to_csv(assignments):
    if assignments:
        df = pd.DataFrame(assignments)
        df.to_csv('deadlines.txt', sep='\t', index=False)
        print("Assignments saved to all_assignments.csv")
    else:
        print("No assignments found.")

# Main program
def run():
    st.title('Assignment Extractor')
    
    username = st.text_input("Enter Enrollment Number")
    password = st.text_input("Enter Password", type="password")
    course_name = st.text_input("Enter Course Name")
    
    if st.button('Extract Assignments'):
        login_to_cms(username, password)
        navigate_to_lms()
    
        assignments = extract_all_courses()
        save_to_csv(assignments)
        st.write(assignments)
        
if __name__ == "__main__":
    username = "02-136232-048"  # Your CMS enrollment number
    password = "Ent@r564"  # Your CMS password

    login_to_cms(username, password)
    navigate_to_lms()
    
    assignments = extract_all_courses()
    save_to_csv(assignments)
    
    driver.quit()

if __name__ == "__main__":
    run()


# In[ ]:




