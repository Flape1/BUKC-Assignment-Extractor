#!/usr/bin/env python
# coding: utf-8

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
import base64
import io

# Initialize session state variables
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'assignments' not in st.session_state:
    st.session_state.assignments = []

def create_webdriver():
    # Configure Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    
    # Setup the webdriver
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
    return True

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
            
            # Extract the download link from cell[2]
            download_link_tag = cells[2].find('a', href=True)
            download_link = download_link_tag['href'] if download_link_tag else None
            
            # If there's a download link, make it a full URL if it's relative
            if download_link and not download_link.startswith('http'):
                download_link = f"https://lms.bahria.edu.pk/Student/{download_link}"

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
    progress_text = st.empty()

    # Refresh the dropdown options each time to avoid stale references
    while True:
        try:
            course_dropdown = wait.until(EC.presence_of_element_located((By.NAME, "courseName")))
            select = Select(course_dropdown)
            options = [option.text.strip() for option in select.options if option.text.strip() and option.text.strip() != "Select Course"]
            break  # Break the loop if the dropdown is successfully located
        except StaleElementReferenceException:
            continue  # Retry if the element went stale

    # Create progress bar
    progress_bar = st.progress(0)
    total_courses = len(options)
    
    # Iterate through all courses
    for i, course_name in enumerate(options):
        progress_text.write(f"Fetching assignments for: {course_name}")
        progress_value = int((i / total_courses) * 100)
        progress_bar.progress(progress_value)

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
            progress_text.write(f"Stale element encountered. Retrying for course: {course_name}")
            continue  # Retry with the next course if the dropdown goes stale
    
    progress_bar.progress(100)
    progress_text.write("All assignments extracted successfully!")
    time.sleep(1)
    progress_text.empty()
    
    return all_assignments

def get_download_link(file_name, df):
    """Generate a link to download the dataframe as a CSV file"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{file_name}">Download CSV File</a>'
    return href

# Main program
def run():
    st.title('Bahria University Assignment Extractor')
    
    # Login section
    if not st.session_state.logged_in:
        with st.form("login_form"):
            st.subheader("Login to CMS")
            username = st.text_input("Enter Enrollment Number")
            password = st.text_input("Enter Password", type="password")
            submit_button = st.form_submit_button("Login & Extract Assignments")
            
            if submit_button:
                if username and password:
                    with st.spinner("Logging in and extracting assignments..."):
                        try:
                            driver = create_webdriver()
                            wait = WebDriverWait(driver, 10)
                            
                            # Login to CMS
                            login_status = login_to_cms(wait, driver, username, password)
                            
                            if login_status:
                                # Navigate to LMS and extract assignments
                                navigate_to_lms(driver)
                                assignments = extract_all_courses(wait, driver)
                                
                                # Store assignments in session state
                                st.session_state.assignments = assignments
                                st.session_state.logged_in = True
                                
                                # Close the driver
                                driver.quit()
                                
                                # Force page rerun to show assignments
                                #st.experimental.rerun()
                                st.legacy_caching.clear_cache()
                            else:
                                st.error("Login failed. Please check your credentials.")
                        except Exception as e:
                            st.error(f"An error occurred: {e}")
                            if 'driver' in locals():
                                driver.quit()
                else:
                    st.warning("Please enter your enrollment number and password.")
    
    # Display assignments if logged in
    else:
        # Add logout button
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.assignments = []
            st.experimental_rerun()
        
        if st.session_state.assignments:
            # Convert to DataFrame for easier handling
            df = pd.DataFrame(st.session_state.assignments)
            
            # Download all as CSV
            st.markdown(get_download_link("all_assignments.csv", df), unsafe_allow_html=True)
            
            # Display assignments grouped by course
            st.subheader("Your Assignments")
            
            # Group by course and display
            courses = df['Course'].unique()
            
            for course in courses:
                with st.expander(f"📚 {course}"):
                    course_assignments = df[df['Course'] == course]
                    
                    for i, row in course_assignments.iterrows():
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**Assignment:** {row['Assignment']}")
                            st.markdown(f"**Deadline:** {row['Deadline']}")
                        
                        with col2:
                            if pd.notna(row['Download Link']):
                                st.markdown(f"[Download]({row['Download Link']})")
                        
                        st.markdown("---")
        else:
            st.info("No assignments found.")

if __name__ == "__main__":
    run()
