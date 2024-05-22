library('haven')
library('readxl')
library('dplyr')
library('randomForest') 
library('caTools')
library('caret')
library('ggplot2')

set.seed(41) # set random seed # for reproducibility

###
# load and slice data
###
Loader <- function(sheetName, PV_num) {
  dev <- getwd()
  data_path <- file.path(dev, 'result', sprintf('preprocessing%s.xlsx', PV_num))
    
  print(paste('>> PV', PV_num, 'READ variable is loaded'))
  df <- read_excel(data_path, sheet=sheetName)
  df$resilient <- as.factor(df$resilient)
  df <- subset(df, select=-c(ESCS))
  summary(df)
  
  df_SK <- df[df$CNT=='Korea', ]
  df_US <- df[df$CNT=='United States', ]
  df_SK <- df_SK[-c(1,2,3)] # CNT, CNTSCHID, CNTSTUID
  df_US <- df_US[-c(1,2,3)] # CNT, CNTSCHID, CNTSTUID
  result <- list('SK' = df_SK, 'US'= df_US)
  return(result)
}

# dfObj = Loader(sheetName = 'full')
dfObj = Loader(sheetName = 'sliced', PV_num="10")

###
# Start Random Forest
####
doRandomForest <- function(inputDf, title, PV_num=10) {
  inputDf[sapply(inputDf, is.character)] <- lapply(inputDf[sapply(inputDf, is.character)], 
                                               as.factor)
  df.roughfix <- na.roughfix(inputDf)
  
  sample = sample.split(df.roughfix$resilient, SplitRatio = 0.7)
  df_train = subset(df.roughfix, sample == TRUE)
  df_test  = subset(df.roughfix, sample == FALSE)
  
  rf <- randomForest(resilient ~.,
                     data = df_train,
                     mtry = floor(sqrt(ncol(df_train))),
                     ntree = 5000,
                     na.action = na.roughfix,
                     importance=TRUE
                     )
  
  pred <- predict(rf, df_test, type="class")
  print(confusionMatrix(pred, df_test$resilient)) # rs1. confusion matrix
  
  dev <- getwd()
  png(filename = file.path(dev, 'result', sprintf('%s_%s.png', title, PV_num))) # desktop
  dev.off() #after using png function, this code line is essential. if not, plot pannel will not show nothing
  
  # importance plot
  db.imp <- importance(rf, type=1)
  df.imp <- data.frame(db.imp)
  df.imp.descending <- df.imp %>% arrange(desc(MeanDecreaseAccuracy))
  df.imp.percentage <- df.imp.descending %>% mutate(Percentage=round(MeanDecreaseAccuracy/sum(MeanDecreaseAccuracy)*100,2))
  print(df.imp.percentage)
  
  plt <- ggplot(df.imp.percentage,
                aes( x = reorder(rownames(df.imp.percentage), Percentage),
                     y = Percentage
                )) +
    geom_col() +
    xlab("variable") +
    coord_flip() + 
    ggtitle(sprintf("Variable Importance Plot__%s__PV%sREAD", title, PV_num))
  
  print(plt)
  
  rs <- list('model'= rf, 'df.mda'= df.imp.percentage) 
  return(rs) # data return as list, first element: randomForest model, seconde element: cleaned dataFrame
}

"
sample test
- run RF and plot
"
rf.SK <- doRandomForest(dfObj$SK, title='South Korea')
rf.US <- doRandomForest(dfObj$US, title='US')

rf.SK$model$importance
rf.SK$df.mda

plot(rf.US$model$err.rate[, 1])
varImpPlot(rf.SK$model,
           sort = T,
           n.var = 10,
           main = "Top 10 - Variable Importance")


"
- 5 iterations are performed with the same data
- RF result comparison file
"
rf_loop <- function(data, title) {
  for (x in 1:5) {
    rf_rs <- doRandomForest(inputDf= data, title=title, PV_num=10)
    rf_rs$df.mda <- subset(rf_rs$df.mda, select=-c(Percentage))
    if (x==1) {
      tmp <- rf_rs$df.mda
      compare_tb <- cbind(predictor = rownames(tmp), tmp)
      rownames(compare_tb) <- 1:nrow(compare_tb)
    } else {
      df <- cbind(predictor = rownames(rf_rs$df.mda), rf_rs$df.mda)
      rownames(df) <- 1:nrow(df)
      compare_tb <- full_join(compare_tb, df, by="predictor")
    }
    
    if (x==5) { # aggregate result
      rs <- compare_tb[, -1]
      rownames(rs) <- compare_tb[,1]
      rs$sumMDA <- rowSums(rs)
      rs2 <- rs %>% select(-contains("MedaDecreaseAccuracy"))
      rs2 <- rs2 %>% mutate(Percentage=round(sumMDA/sum(sumMDA)*100,2))
      rs3 <- rs2[,-c(1, 2, 3, 4, 5)]
    }
  }
  return(rs3)
}

rs_loop_SK <- rf_loop(dfObj$SK, title='South Korea')
rs_loop_US<- rf_loop(dfObj$US, title='United States')


"
- analysis is performed by 10 PVs.
- RF result comparison_v2 file
"
rf_loop2 <- function() {
  for (x in 1:10) {
    dfObj = Loader(sheetName = 'sliced', PV_num=as.character(x))
    rs_SK <- doRandomForest(inputDf= dfObj$SK, title="South Korea", PV_num=x)
    rs_US <- doRandomForest(inputDf= dfObj$US, title="United States", PV_num=x)
    
    rs_SK2 <- subset(rs_SK$df.mda, select=-c(Percentage))
    rs_US2 <- subset(rs_US$df.mda, select=-c(Percentage))
    if (x==1) {
      compare_tb_SK <- cbind(predictor = rownames(rs_SK2), rs_SK2)
      compare_tb_US <- cbind(predictor = rownames(rs_US2), rs_US2)
      rownames(compare_tb_SK) <- 1:nrow(compare_tb_SK)
      rownames(compare_tb_US) <- 1:nrow(compare_tb_US)
    } else {
      df_SK <- cbind(predictor = rownames(rs_SK2), rs_SK2)
      df_US <- cbind(predictor = rownames(rs_US2), rs_US2)
      rownames(df_SK) <- 1:nrow(df_SK)
      rownames(df_US) <- 1:nrow(df_US)
      compare_tb_SK <- full_join(compare_tb_SK, df_SK, by="predictor")
      compare_tb_US <- full_join(compare_tb_US, df_US, by="predictor")
    }
    
    if (x==10) { # aggregate result
      rs_SK <- compare_tb_SK[, -1]
      rs_US <- compare_tb_US[, -1]
      rownames(rs_SK) <- compare_tb_SK[,1]
      rownames(rs_US) <- compare_tb_US[,1]
      rs_SK$sumMDA <- rowSums(rs_SK)
      rs_US$sumMDA <- rowSums(rs_US)
      rs2_SK <- rs_SK %>% select(-contains("MedaDecreaseAccuracy"))
      rs2_US <- rs_US %>% select(-contains("MedaDecreaseAccuracy"))
      rs2_SK <- rs2_SK %>% mutate(Percentage=round(sumMDA/sum(sumMDA)*100,2))
      rs2_US <- rs2_US %>% mutate(Percentage=round(sumMDA/sum(sumMDA)*100,2))
      rs3_SK <- rs2_SK[,-c(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)]
      rs3_US <- rs2_US[,-c(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)]
      final_rs <- list('SK'= rs3_SK, 'US'= rs3_US)
    }
  }
  return(final_rs)
}
rs_loop2 <- rf_loop2()