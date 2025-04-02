#!/usr/bin/env python
# coding: utf-8

# In[33]:

import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import StaleElementReferenceException
import time
from bs4 import BeautifulSoup
import pandas as pd

def create_webdriver():
    # Configure Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # For Streamlit Cloud deployment
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    
    # Setup the webdriver - no need to specify service or binary location
    driver = webdriver.Chrome(options=chrome_options)
    
    return driver

# CMS Login URL
cms_url = "https://cms.bahria.edu.pk/Logins/Student/Login.aspx"
lms_url = "https://lms.bahria.edu.pk/Student/Assignments.php"

# Step 1: Login to CMS
def login_to_cms(wait, driver, username, password):
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
    time.sleep(2)  # Wait for the login to complete
    
# Step 2: Navigate to LMS and open Assignments
def navigate_to_lms(driver):
    driver.get("https://cms.bahria.edu.pk/Sys/Common/GoToLMS.aspx")
    time.sleep(2)  # Wait for LMS to load

# Step 3: Extract assignments for a given course
def extract_assignments(driver):
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
             # Extract the download link from cell[3]
            download_link_tag = cells[2].find('a', href=True)  # Assuming the download link is in cell[3]
            download_link = download_link_tag['href'] if download_link_tag else None

            assignments_data.append({
                "Assignment": assignment_name,
                "Deadline": deadline,
                "Download Link": download_link
            })

    
    return assignments_data

# Step 4: Extract assignments for all courses
def extract_all_courses(wait, driver):
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
        st.write(f"Fetching assignments for: {course_name}")

        # Refresh dropdown each time to prevent stale element issues
        course_dropdown = wait.until(EC.presence_of_element_located((By.NAME, "courseName")))
        select = Select(course_dropdown)
        
        try:
            select.select_by_visible_text(course_name)
            time.sleep(0.5)  # Give it some time to load the assignments page

            # Extract assignments
            assignments = extract_assignments(driver)
            for assignment in assignments:
                assignment["Course"] = course_name
                all_assignments.append(assignment)

        except StaleElementReferenceException:
            print(f"Stale element encountered. Retrying for course: {course_name}")
            continue  # Retry with the next course if the dropdown goes stale

    return all_assignments

# Step 5: Save assignments to a CSV
# Step 5: Save assignments to a CSV and provide download option
# Step 5: Save assignments to a CSV and provide download option
def save_to_csv(assignments):
    if assignments:
        df = pd.DataFrame(assignments)
        
        # Display assignments table in Streamlit
        st.write("### Extracted Assignments")
        
        for index, row in df.iterrows():
            st.write(f"**Course:** {row['Course']}")
            st.write(f"**Assignment:** {row['Assignment']}")
            st.write(f"**Deadline:** {row['Deadline']}")
            if pd.notna(row['Download Link']):
                download_url = row['Download Link']
                
                # Use Streamlit's download_button for downloading directly
                # Provide download button for each assignment
                st.download_button(
                    label="Download Assignment: " + row['Assignment'],
                    data=download_url,
                    file_name=row['Assignment'] + ".pdf",  # Assuming the file extension is .pdf (change if needed)
                    mime='application/octet-stream',  # or the appropriate MIME type
                )
            else:
                st.write("No downloadable file available.")

            st.write("---")
        
        # Save the dataframe to a CSV file
        csv_file = df.to_csv(index=False).encode('utf-8')
        
        # Provide download option for the CSV file
        """st.download_button(
            label="Download All Assignments as CSV",
            data=csv_file,
            file_name='all_assignments.csv',
            mime='text/csv'
        )"""
    else:
        st.write("No assignments found.")



# Main program
def run():
    st.title('Assignment Extractor')
    if 'assignments_extracted' not in st.session_state:
            st.session_state.assignments_extracted = False
    try:
        driver = create_webdriver()
        wait = WebDriverWait(driver, 10)
    
        if not st.session_state.assignments_extracted:
        
            
            
            username = st.text_input("Enter Enrollment Number")
            password = st.text_input("Enter Password", type="password")
            
            if st.button('Extract Assignments'):
                login_to_cms(wait, driver,username, password)
                navigate_to_lms(driver)
            
                assignments = extract_all_courses(wait, driver)
                save_to_csv(assignments)
            st.session_state.assignments_extracted = True
        else:
            st.write("Assignments have already been extracted.")
        driver.quit()
    
    except Exception as e:
        st.error(f"An error occurred: {e}")
        
if __name__ == "__main__":
    run()


# In[ ]:




