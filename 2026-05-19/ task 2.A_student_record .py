from numpy import mean
# student details
student_name = "Arun"
student_age = 20
student_marks = [85.5, 90.0, 78.2]

#Storing all details inside a dictionary.
student_details = {
    "Name": student_name,
    "Age": student_age,
    "Marks": student_marks
}

#Checking the data type of each value.
print(f"Type of Name: {type(student_details['Name'])}")
print(f"Type of Age: {type(student_details['Age'])}")
print(f"Type of Marks: {type(student_details['Marks'])}")

#Calculateing total marks and average marks.
Total_marks = sum(student_details["Marks"])
Average_marks = mean (student_details["Marks"])
print(f"Total Marks: {Total_marks}")
print(f"Average Marks: {Average_marks}")


#Checking if the student has passed or failed based on average marks.
if Average_marks >= 40:
    print("The student has passed.")
else:    
    print("The student has failed.")   

#Printing induvidual marks
for marks in student_details["Marks"]:
    print(f"Mark: {marks}")    

#Converting the marks list to a set and printing it.
marks = set (student_details["Marks"])
print(f"Marks: {marks}")

#Storeing subject names in a tuple and printing them.
subject_names = ("Math", "Science", "English")
print(f"Subject Names: {subject_names}")

#Adding a variable remarks = None and printing its type.
remarks = None
print(f"Remarks: {remarks}")
print(f"Type of Remarks: {type(remarks)}")

#Using a boolean is_passed = True or False and printing its type.
is_passed = True
print(f"Is Passed: {is_passed}")
print(f"Type of Is Passed: {type(is_passed)}")

#Formatted student report.
print("Student Report")
print("--------------")
print(f"Name: {student_details['Name']}")
print(f"Age: {student_details['Age']}")
print(f"Total Marks: {Total_marks}")
print(f"Average Marks: {Average_marks}")
print(f"Remarks: {remarks}")
print(f"Passed: {is_passed}")