#!/usr/bin/env python
# coding: utf-8

import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import StaleElementReferenceException
import time
from bs4 import BeautifulSoup
import pandas as pd

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

    driver.find_element(By.ID, "BodyPH_btnLogin").click()
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

# Main program
def run():
    st.set_page_config(
        page_title="BUKC Assignment Extractor",
        page_icon="📚",
        layout="wide"
    )
    
    st.title('Bahria University Assignment Extractor')
    
    # Add custom CSS for overall styling
    st.markdown("""
    <style>
        /* Main container styling */
        .main {
            background-color: #f8f9fa;
        }
        
        /* Security note styling */
        .security-note {
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 25px;
            border-left: 4px solid #2196f3;
        }
        
        /* Button styling */
        .stButton > button {
            background-color: #2196f3;
            color: white;
            border-radius: 5px;
            padding: 0.5rem 1rem;
            border: none;
            transition: all 0.3s ease;
            width: 100%;
        }
        
        .stButton > button:hover {
            background-color: #1976d2 !important;
            color: white !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        
        /* Text input styling */
        .stTextInput > div > div > input {
            border-radius: 5px;
            border: 1px solid #bdbdbd;
            padding: 0.5rem;
            transition: all 0.3s ease;
        }
        
        .stTextInput > div > div > input:hover,
        .stTextInput > div > div > input:focus {
            border-color: #2196f3 !important;
            box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.2);
        }
        
        /* Form container styling */
        .stForm {
            background-color: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        /* Assignment card styling */
        .assignment-card {
            background-color: white;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        
        .assignment-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        
        /* Download link styling */
        .download-link {
            color: #2196f3;
            text-decoration: none;
            font-weight: 500;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            background-color: #e3f2fd;
            display: inline-block;
            margin-top: 0.5rem;
            transition: all 0.3s ease;
        }
        
        .download-link:hover {
            background-color: #bbdefb;
            text-decoration: none;
        }

        /* Dropdown styling */
        .stSelectbox > div > div > div {
            border-radius: 5px;
            border: 1px solid #bdbdbd;
            transition: all 0.3s ease;
        }
        
        .stSelectbox > div > div > div:hover {
            border-color: #2196f3 !important;
            box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.2);
        }

        /* Expander styling */
        .streamlit-expanderHeader {
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 0.5rem;
            margin-bottom: 0.5rem;
            transition: all 0.3s ease;
        }
        
        .streamlit-expanderHeader:hover {
            background-color: #e3f2fd !important;
        }

        /* Progress bar styling */
        .stProgress > div > div > div {
            background-color: #2196f3;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Add security note with improved styling
    st.markdown("""
    <div class="security-note">
        <p style='color: #0d47a1; margin: 0;'>
            <span style='font-size: 1.2em;'>🔒</span> 
            <strong>Security Note:</strong> This app does not store your password or any login credentials. 
            All data is processed in real-time and is not saved anywhere.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Login section with improved styling
    if not st.session_state.logged_in:
        with st.form("login_form"):
            st.subheader("Login to CMS")
            st.markdown("""
            <div style='margin-bottom: 1.5rem;'>
                Please enter your CMS credentials to view your assignments.
            </div>
            """, unsafe_allow_html=True)
            
            username = st.text_input("Enter Enrollment Number", placeholder="e.g., 12345")
            password = st.text_input("Enter Password", type="password", placeholder="Enter your password")
            
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
                                st.rerun()
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
        # Add logout button with improved styling
        if st.button("Logout", key="logout_button"):
            st.session_state.logged_in = False
            st.session_state.assignments = []
            st.rerun()
        
        if st.session_state.assignments:
            # Convert to DataFrame for easier handling
            df = pd.DataFrame(st.session_state.assignments)
            
            # Display assignments grouped by course with improved styling
            st.subheader("Your Assignments")
            
            # Group by course and display
            courses = df['Course'].unique()
            
            for course in courses:
                with st.expander(f"📚 {course}", expanded=True):
                    course_assignments = df[df['Course'] == course]
                    
                    for i, row in course_assignments.iterrows():
                        st.markdown("""
                        <div class="assignment-card">
                            <div style='margin-bottom: 0.5rem;'>
                                <strong style='color: #2196f3;'>Assignment:</strong> {assignment}
                            </div>
                            <div style='margin-bottom: 0.5rem;'>
                                <strong style='color: #2196f3;'>Deadline:</strong> {deadline}
                            </div>
                            {download_link}
                        </div>
                        """.format(
                            assignment=row['Assignment'],
                            deadline=row['Deadline'],
                            download_link=f'<a href="{row["Download Link"]}" class="download-link" target="_blank">Download Assignment</a>' if pd.notna(row['Download Link']) else ''
                        ), unsafe_allow_html=True)
        else:
            st.info("No assignments found.")

if __name__ == "__main__":
    run()
