%run ./12-idempotent-to-bronze

class kafkaToBronzeTestSuite():
    def __init__(self):
        self.base_data_dir = "/FileStore/data_spark_streaming_scholarnest"
     
    def cleanTests(self):
        print(f"Starting Cleanup...", end='')
        spark.sql("drop table if exists invoices_bz")
        dbutils.fs.rm("/user/hive/warehouse/invoices_bz", True)
        dbutils.fs.rm(f"{self.base_data_dir}/chekpoint/invoices_bz", True)
        print("Done")

    def assertResult(self, expected_count):
        print(f"\tStarting validation...", end='')
        actual_count = spark.sql("select count(*) from invoices_bz").collect()[0][0]
        assert expected_count == actual_count, f"Test failed! actual count is {actual_count}"
        print("Done")

    def waitForMicroBatch(self, sleep=30):
        import time
        print(f"\tWaiting for {sleep} seconds...", end='')
        time.sleep(sleep)
        print("Done.") 
    
    def runTests(self):
        self.cleanTests()
        bzStream = Bronze()
        value_schema = bzStream.getSchema()
        spark.sql(f"CREATE TABLE invoices_bz (key STRING, value STRUCT<{value_schema}>, topic STRING, timestamp TIMESTAMP)")

        print("Testing Scenario - Start from beginneing on a new checkpoint...") 
        bzQuery = bzStream.process()
        self.waitForMicroBatch() 
        bzQuery.stop()     
        self.assertResult(30)
        print("Validation passed.\n")

        print("Testing Scenarion - Restart from where it stopped on the same checkpoint...")
        bzQuery = bzStream.process()
        self.waitForMicroBatch()
        bzQuery.stop()
        self.assertResult(30)
        print("Validation passed.\n") 

        print("Testing Scenario - Start from 1697945539000 on a new checkpoint...") 
        dbutils.fs.rm(f"{self.base_data_dir}/chekpoint/invoices_bz", True)
        bzQuery = bzStream.process(1697945539000)
        self.waitForMicroBatch()
        bzQuery.stop()
        self.assertResult(30)
        print("Validation passed.\n")


ts = kafkaToBronzeTestSuite()
ts.runTests()
