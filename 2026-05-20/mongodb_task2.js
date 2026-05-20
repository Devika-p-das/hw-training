// using database companyDB
use companyDB

// inserting one employee document
db.employees.insertOne({
  empId: 101,
  name: "Ravi",
  department: "IT",
  salary: 75000,
  isActive: true
})

// inserting multiple employee documents
db.employees.insertMany([{
empId:102,
name:"Devi",
department:"Mathematics",
salary:80000,
isActive:true
  },
{
  empId: 104,
    name: "Meera",
    department: "Finance",
    salary: 72000,
    isActive: false
  },
  {
    empId: 105,
    name: "Suresh",
    department: "IT",
    salary: 80000,
    isActive: true
  },
  {
    empId: 106,
    name: "Neha",
    department: "Marketing",
    salary: 45000,
    isActive: false
  }
])

//update salary of all employees in IT department by increasing it by 10%
db.employees.updateMany(
  { department: "IT" },
  { $mul: { salary: 1.10 } }
)

//delete all employees who are not active
db.employees.deleteMany({
  isActive: false
})

// find all employees and display them in a readable format
db.employees.find().pretty()

//  Create single field index on department
db.employees.createIndex({ department: 1 })


//  Create compound index on department and salary
db.employees.createIndex({ department: 1, salary: 1 })


// Validate indexes
db.employees.getIndexes()

//-------------------------------------------------------------------------------------------------------------------------------------------------------------

/// Teminal commands for the task2part2
/// Export JSON
// mongoexport --db=companyDB --collection=employees --out=employees.json

// /Export CSV
// mongoexport --db=companyDB --collection=employees --type=csv --fields=empId,name,department,salary,isActive --out=employees.csv

// /Database Dump
// mongodump --db=companyDB --out=backup

// /Drop Database
//use companyDB
//db.dropDatabase()

/// Restore Database
// mongorestore --db companyDB backup/companyDB

/// Import JSON
// mongoimport --db=companyDB --collection=importedEmployees --file=employees.json