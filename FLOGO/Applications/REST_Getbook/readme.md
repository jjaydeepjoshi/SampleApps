REST API Sample

This sample is modeled on sample BookStore application and invoke a REST API at the backend that delivers sample JSON data. This backend REST API is hosted at - hosted at https://my-json-server.typicode.com/tibcosoftware/tci-flogo/Book

First you will need to upload Throw Error Extention from 
github.com/TIBCOSoftware/flogo-contrib/activity/error

If you run any of these samples locally using TIBCO Flogo® Enterprise -

To Get all Books - You will need to hit the url - http://localhost:9999/books/

To Get Book By ISBN - you will need to hit the url - http://localhost:9999/books/1451648537

If you want to test Error Handler, you can hit the above url with Invalid ISBN number like http://localhost:9999/books/999

You can check the sample JSON data for correct ISBN to be used while testing the samples - https://my-json-server.typicode.com/tibcosoftware/tci-flogo/Book
Import a sample

Download the flogo.sample.rest_getBooks.json file.

Create a new empty app. Create an app

On the app details page, select Import app. Select import

Browse on your machine or drag and drop the .json file for the app that you want to import. Import your sample

Click Upload. The Import app dialog displays some generic errors and warnings as well as any specific errors or warnings pertaining to the app you are importing. It validates whether all the activities and triggers used in the app are available in the Extensions tab. The Import app dialog

You have the option to import all flows from the source app or selectively import flows.

Click Next. If you had not selected a trigger in the previous dialog, the flows associated with that trigger are displayed. You have the option to select one or more of these flows such that the flows get imported as blank flows that are not attached to any trigger. By default, all flows are selected. Clear the check box for the flows that you do not want to import. If your flow(s) have subflows, and you select only the main flow but do not select the subflow, the main flow gets imported without the subflow. Click Next.
