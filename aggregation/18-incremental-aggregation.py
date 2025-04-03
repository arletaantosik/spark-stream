class Bronze():
    def __init__(self):
        self.base_data_dir = "/FileStore/data_spark_streaming_scholarnest"

    def getSchema(self):
        return """InvoiceNumber string, CreatedTime bigint, StoreID string, PosID string, CashierID string,
                CustomerType string, CustomerCardNo string, TotalAmount double, NumberOfItems bigint, 
                PaymentMethod string, TaxableAmount double, CGST double, SGST double, CESS double, 
                DeliveryType string,
                DeliveryAddress struct<AddressLine string, City string, ContactNumber string, PinCode string, 
                State string>,
                InvoiceLineItems array<struct<ItemCode string, ItemDescription string, 
                    ItemPrice double, ItemQty bigint, TotalValue double>>
            """

    def readInvoices(self):
        from pyspark.sql.functions import input_file_name
        return (spark.readStream
                    .format("json")
                    .schema(self.getSchema())
                    .load(f"{self.base_data_dir}/data/invoices")
                    .withColumn("InputFile", input_file_name())
                )  

    def process(self):
        print(f"\nStarting Bronze Stream...", end='')
        invoicesDF = self.readInvoices()
        sQuery =  ( invoicesDF.writeStream
                            .queryName("bronze-ingestion")
                            .option("checkpointLocation", f"{self.base_data_dir}/chekpoint/invoices_bz")
                            .outputMode("append")
                            .toTable("invoices_bz")           
                    ) 
        print("Done")
        return sQuery   
       

# COMMAND ----------

class Gold():
    def __init__(self):
        self.base_data_dir = "/FileStore/data_spark_streaming_scholarnest"
        
    def readBronze(self):
        return spark.readStream.table("invoices_bz")

    def getAggregates(self, invoices_df):
        from pyspark.sql.functions import sum, expr
        return (invoices_df.groupBy("CustomerCardNo")
                    .agg(sum("TotalAmount").alias("TotalAmount"),
                         sum(expr("TotalAmount*0.02")).alias("TotalPoints"))
                )

    def upsert(self, rewards_df, batch_id):
        rewards_df.createOrReplaceTempView("customer_rewards_df_temp_view")
        merge_statement = """MERGE INTO customer_rewards t
                USING customer_rewards_df_temp_view s
                ON s.CustomerCardNo == t.CustomerCardNo
                WHEN MATCHED THEN
                UPDATE SET t.TotalAmount = s.TotalAmount, t.TotalPoints = s.TotalPoints
                WHEN NOT MATCHED THEN
                INSERT *
            """
        rewards_df._jdf.sparkSession().sql(merge_statement)

    def process(self):
        invoices_df = self.readBronze()
        aggregate_df = self.getAggregates(invoices_df)
        sQuery = (aggregate_df.writeStream
                        .queryName("gold-update")
                        .option("checkpointLocation", f"{self.base_data_dir}/chekpoint/customer_rewards")
                        .outputMode("update") #only new/updated data for each batch will be in the table
                        .foreachBatch(self.upsert)
                        .start()
                  )
        return sQuery
